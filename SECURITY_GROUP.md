# 安全组配置说明（Security Group）

ElastiCache Valkey 集群部署在 VPC 内，**只能从 VPC 内部访问**（无法直接从公网访问）。正确的安全组配置是连接成功和保障安全的前提。

> 本文中的 `sg-xxxxxxxx`、`vpc-xxxxxxxx` 均为占位符，请替换为你自己的资源 ID。

---

## 网络访问模型

```
┌──────────────────────────── VPC ────────────────────────────┐
│                                                              │
│   ┌─────────────────┐        TCP 6379       ┌────────────┐   │
│   │  应用 (EC2/      │ ───────────────────▶ │ ElastiCache │   │
│   │  Lambda/ECS)    │                       │  Valkey 9.0 │   │
│   │  sg-APP         │                       │  sg-CACHE   │   │
│   └─────────────────┘                       └────────────┘   │
│                                                              │
└──────────────────────────────────────────────────────────────┘
        ▲
        │ SSH 隧道 (-L 8501:localhost:8501) 访问 Dashboard
   ┌────┴─────┐
   │ 本地浏览器 │  （仅用于访问 Streamlit，不直连 6379）
   └──────────┘
```

---

## 核心入站规则

在 **ElastiCache 所用的安全组**（`sg-CACHE`）上，放行来自**应用安全组**（`sg-APP`）的 TCP 6379：

| 方向 | 协议 | 端口 | 来源 | 用途 |
|------|------|------|------|------|
| 入站 | TCP | 6379 | `sg-APP`（应用安全组） | Valkey 客户端连接 |

> 本 Demo 中应用和缓存使用了同一个安全组，因此规则的 Source 指向安全组自身（同组内互通）。

### CLI 配置

```bash
# 放行同安全组内的 6379 访问
aws ec2 authorize-security-group-ingress \
  --group-id sg-xxxxxxxx \
  --protocol tcp --port 6379 \
  --source-group sg-xxxxxxxx \
  --region cn-northwest-1
```

如果应用和缓存使用不同安全组：

```bash
aws ec2 authorize-security-group-ingress \
  --group-id sg-CACHE \
  --protocol tcp --port 6379 \
  --source-group sg-APP \
  --region cn-northwest-1
```

---

## CloudFormation 中的安全组规则

`cloudformation.yaml` 通过 `AWS::EC2::SecurityGroupIngress` 资源自动创建该规则：

```yaml
ElastiCacheIngressRule:
  Type: AWS::EC2::SecurityGroupIngress
  Properties:
    GroupId: !Ref AppSecurityGroupId
    IpProtocol: tcp
    FromPort: 6379
    ToPort: 6379
    SourceSecurityGroupId: !Ref AppSecurityGroupId
    Description: Allow Valkey access within the same security group
```

---

## 安全最佳实践

1. **绝不对 `0.0.0.0/0` 开放 6379**
   Valkey/Redis 协议默认无强认证，公网暴露的 6379 端口会在数分钟内被扫描攻击（挖矿、勒索、数据窃取）。务必用安全组限制来源。

2. **使用安全组引用而非 CIDR**
   优先用 `--source-group`（引用应用安全组）而非固定 IP 段，更易随实例伸缩维护。

3. **生产环境启用传输加密**
   本 Demo 为简化设置 `TransitEncryptionEnabled: false`。生产环境应启用 TLS（`--transit-encryption-enabled`）并配合 RBAC/AUTH。

4. **启用静态加密**
   CF 模板已默认 `AtRestEncryptionEnabled: true`。

5. **Dashboard 访问走 SSH 隧道**
   Streamlit（8501 端口）不要直接公网暴露，通过 `ssh -L` 端口转发到本地访问。

6. **最小权限子网**
   ElastiCache 放在私有子网，不分配公网路由。

---

## 排错

| 现象 | 可能原因 |
|------|---------|
| 连接超时 | 安全组未放行 6379，或应用不在同 VPC |
| `Connection refused` | endpoint 错误，或集群未就绪 |
| `Connection closed by server` | 客户端兼容性问题，CLI 改用 redis-py |
| 可 PING 通但无法搜索 | 小实例未配置 `reserved-memory-percent` |

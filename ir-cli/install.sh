#!/usr/bin/env bash
# ir-cli 一键安装/升级脚本
#
# 用法（本地执行或 curl | bash 均可）:
#   ./install.sh                                   # 默认从 github 安装（默认分支）
#   ./install.sh --repo gitee                      # 国内设备走 gitee
#   ./install.sh --ref dev                         # 指定分支/tag/commit
#   ./install.sh --base-url https://ir.example.com # 顺便写入服务端地址
#
#   curl -LsSf https://raw.githubusercontent.com/gujialind/InvestRing/main/ir-cli/install.sh \
#     | bash -s -- --repo gitee --ref dev --base-url https://ir.example.com
#
# 升级 = 重跑本脚本（--force --reinstall 会强制拉取仓库最新提交）。
# ~/.ir/ 下的 token 与配置不受安装/升级影响。
set -euo pipefail

REPO="github"
REF=""
BASE_URL="${IR_BASE_URL:-}"

usage() {
    sed -n '2,14p' "$0" | sed 's/^# \{0,1\}//'
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --repo)     REPO="$2"; shift 2 ;;
        --ref)      REF="$2"; shift 2 ;;
        --base-url) BASE_URL="$2"; shift 2 ;;
        -h|--help)  usage; exit 0 ;;
        *) echo "未知参数: $1（--help 查看用法）" >&2; exit 1 ;;
    esac
done

# 指定 --ref 时拼接 @ref（pip 风格 git URL）；缺省为远端默认分支
AT_REF=""
[[ -n "$REF" ]] && AT_REF="@${REF}"

case "$REPO" in
    github) GIT_URL="git+ssh://git@github.com/gujialind/InvestRing.git${AT_REF}#subdirectory=ir-cli" ;;
    gitee)  GIT_URL="git+ssh://git@gitee.com/collyns_Gu/invest-ring.git${AT_REF}#subdirectory=ir-cli" ;;
    git+*)
        # 完整 URL 由调用方自带 @ref，不另行拼接，避免产生双 @
        if [[ -n "$REF" ]]; then
            echo "错误: --ref 仅适用于 github/gitee 预设，完整 URL 请直接写入 @ref（如 ...git@dev#subdirectory=...）" >&2
            exit 1
        fi
        GIT_URL="$REPO"
        ;;
    *) echo "无效 --repo: $REPO（可选 github / gitee / git+... 完整 URL）" >&2; exit 1 ;;
esac

# ---------- 前置检查 ----------
if ! command -v git >/dev/null 2>&1; then
    echo "错误: 需要 git（从仓库拉取源码），请先安装 git" >&2
    exit 1
fi

# ---------- 安装器选择: uv > pipx > 自动装 uv ----------
if command -v uv >/dev/null 2>&1; then
    echo "==> 使用 uv 安装 ir-cli ..."
    uv tool install --force --reinstall "$GIT_URL"
elif command -v pipx >/dev/null 2>&1; then
    echo "==> 使用 pipx 安装 ir-cli ..."
    pipx install --force "$GIT_URL"
else
    echo "==> 未检测到 uv / pipx，先安装 uv ..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
    uv tool install --force --reinstall "$GIT_URL"
fi

# ---------- 写入服务端地址（等价于 ir_cli.config.save_config） ----------
if [[ -n "$BASE_URL" ]]; then
    IR_DIR="$HOME/.ir"
    mkdir -p "$IR_DIR" && chmod 700 "$IR_DIR"
    CONF="$IR_DIR/config"
    if [[ -f "$CONF" ]] && grep -q '^base_url=' "$CONF"; then
        sed -i.bak "s|^base_url=.*|base_url=${BASE_URL}|" "$CONF" && rm -f "$CONF.bak"
    else
        echo "base_url=${BASE_URL}" >>"$CONF"
    fi
    echo "==> 已写入 $CONF: base_url=${BASE_URL}"
fi

# ---------- 验证 ----------
if command -v ir >/dev/null 2>&1; then
    echo "==> 安装完成: $(command -v ir)"
else
    echo "==> 安装完成，但 ir 不在当前 PATH 中。"
    echo "    请将 ~/.local/bin 加入 PATH 后重开终端: export PATH=\"\$HOME/.local/bin:\$PATH\""
fi

if [[ -z "$BASE_URL" ]]; then
    echo "提示: 尚未配置服务端地址，可重跑脚本加 --base-url，或手动写入 ~/.ir/config"
fi
echo "下一步: ir auth login"

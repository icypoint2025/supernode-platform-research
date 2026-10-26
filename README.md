# 超节点产品研究

完整公开阅读版：产品介绍、全场景旅程、竞品分析与设计策略。

网站地址：[打开完整报告](https://icypoint2025.github.io/supernode-platform-research/)。

## 自动发布

网站位于 `projects/supernode-report/`。默认分支的站点文件更新后，GitHub Actions核对资源摘要、依赖与脚本语法，再按完整清单发布。公开内容仅含报告、截图和前端交互。MRD原表、厂商手册、PPT及原始逐行提取数据保留在本地，出处以文字说明保留。原项目中的本地文字写回服务也保留在电脑上。

原报告修改保存后，在原项目运行：

```sh
./.venv/bin/python scripts/publish_github_pages.py --repository ../超节点公网网站
```

同步命令会核对远程地址、默认分支与清洁状态；推送中断后可重跑，分叉或清单外文件会直接停止。撤下旧资源时先列出文件，经核对后使用 `--allow-remove-generated` 明确批准，仅移除旧清单里的生成文件。

## 本地验证

```sh
python3 tools/validate_site.py projects/supernode-report --stage _site
python3 -m http.server 8080 --directory _site
```

需要Python3和Node.js，`_site`必须是全新目录。

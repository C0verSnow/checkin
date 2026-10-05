# 本文档为4象限的任务清单，全文书写大白话

## 想做：
- 完成 issue #3：保存能离线打开的搜索页，视频链接联网访问原网站。
- 完成 issue #1：用两个 Python 脚本保存抖音和 B 站“罗生门”搜索页。
- 更新使用说明，在 GitHub 的 Linux 环境跑测试，提交 PR 并处理 issue。

## 做完：
- issue #3：已按用户回复确认保存静态页面，不要求离线登录、继续搜索或播放视频。
- issue #3：已在 fix 分支补上内嵌 CSS、嵌套图片和字体、SVG 图标、资源报告以及原网站视频链接。
- issue #3：已更新使用说明和远端测试，测试会在断网的新浏览器中直接打开 HTML。
- 2026-10-05：仓库已克隆到 E:\git\checkin，本地在 main 分支工作。
- 已读 issue 和仓库文件，确认仓库目前只有 README，没有现成的测试流程。
- 已查看 CloakBrowser 官方说明，确认安装方式和浏览器调用方法。
- 已完成 douyin.py、bilibili.py 和共用的安装、保存代码，支持输出位置和等待时间设置。
- 已更新 README，说明 Linux 安装、使用方法、HTML 下载和登录限制。
- 已新增 GitHub Linux 工作流：8 个单元测试和真实 CloakBrowser 渲染测试通过，两个网站抓取均通过。
- push 流程：https://github.com/huan00000/checkin/actions/runs/37318746790 。
- PR 流程：https://github.com/huan00000/checkin/actions/runs/37318785381 。
- 已下载并检查 HTML：B 站 1,133,306 字节，包含搜索结果和视频链接；抖音 765,616 字节，保存搜索页，但提示登录后才能搜索更多视频。
- 两个 HTML 已放在本地 output 目录，不加入 Git；远端流程中也能下载附件。
- 已提交 PR #2：https://github.com/huan00000/checkin/pull/2 ，尚未合并。
- issue #1 已按要求关闭：https://github.com/huan00000/checkin/issues/1 。

## 没做：
- 按用户约定，不做本地构建、编译或会触发编译的测试。
- 没有自动登录抖音；本次保存的是网站实际返回的搜索页面。

## 在做：
- 2026-10-05：开始处理 issue #3，已更新仓库并切换到 fix 分支。
- 已提交 PR #4：https://github.com/huan00000/checkin/pull/4 。
- 正在跑远端测试，并补上两个真实网站 HTML 的断网打开检查和截图。

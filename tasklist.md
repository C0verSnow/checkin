# 本文档为4象限的任务清单，全文书写大白话

## 想做：
- C0verSnow/checkin issue #1：用 CloakBrowser 打开抖音登录，保存二维码，输入指定手机号，点击一次发送验证码并保存结果 PNG。
- 完成 issue #3：保存能离线打开的搜索页，视频链接联网访问原网站。
- 完成 issue #1：用两个 Python 脚本保存抖音和 B 站“罗生门”搜索页。
- 更新使用说明，在 GitHub 的 Linux 环境跑测试，提交 PR 并处理 issue。

## 做完：
- issue #3：已完成，PR #4 已提交但尚未合并：https://github.com/huan00000/checkin/pull/4 。issue #3 已按要求关闭。
- issue #3：最终代码提交 c5ccebc 的远端 Linux CI 全部通过：https://github.com/huan00000/checkin/actions/runs/37321991421 。12 个单元测试、真实浏览器断网打开测试、两站抓取和断网打开检查均通过。
- issue #3：抖音保存 349 个资源、29 张图片和 40 个联网链接，当前页面需要的资源没有失败，没有可见坏图或外部请求。网站当时返回登录提示页；另有 1 张未用于当前可见元素或伪元素的 CSS 图片超时，已单独留在报告中。
- issue #3：已下载最终 HTML、资源报告、检查报告和截图到 E:\git\checkin\output，已查看两站截图。HTML 可双击离线查看，视频链接联网访问原网站。
- issue #3：2026-10-05 已完成静态阅读和 git diff --check，没有进行本地编译验证。
- issue #3：远端单元测试和断网浏览器测试通过；B 站实际页面通过，173 个资源、49 张图片、170 个联网链接，无资源失败、坏图或外部请求，已查看截图。
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
- 已提交 PR #2：https://github.com/huan00000/checkin/pull/2 ，开始 issue #3 前已合并。
- issue #1 已按要求关闭：https://github.com/huan00000/checkin/issues/1 。

## 没做：
- 按用户约定，不做本地构建、编译或会触发编译的测试。
- 没有自动登录抖音；本次保存的是网站实际返回的搜索页面。

## 在做：
- 2026-10-08：已克隆当前仓库，切到 feature/issue-1-douyin-login，读完 issue 和已有脚本。正在新增登录截图脚本和远端检查；不做本地编译验证。
- 无。issue #3 的代码、文档、远端验证、PR 和关闭 issue 均已完成。

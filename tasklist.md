# 本文档为4象限的任务清单，全文书写大白话

## 想做：
- 本次 issue 的二维码要求已完成，暂无新增任务。

## 做完：
- 已读取仓库约定和用户指定的 TDD 技能及测试说明。
- 已确认本地仓库对应 C0verSnow/checkin，工作分支是 feature/issue-3-login-api，开始时没有未提交改动。
- 已读取 issue #3、现有 PR #4、登录脚本、接口脚本、测试和远端工作流。
- 已发现现有流程由浏览器发送验证码，requests 只验证二维码；这和 issue 要求 requests 能发送验证码存在差别。
- 用户已明确按 issue 完成 requests 发送验证码和保存二维码，并同意浏览器登录入口与 requests 接口入口两个测试范围；测试在远端 CI 跑。
- 第一个测试已改为检查：浏览器记录真实请求后，明确开启发送的 requests 能保存二维码并发送一次；再次运行同一请求文件不能重复发送。
- TDD 红灯已确认：提交 dfd0071 的远端测试 https://github.com/C0verSnow/checkin/actions/runs/37948138076 ，新测试在 requests 发送前得到 ValueError，其他 11 个测试通过。
- 已做最小修改：明确传入发送参数时允许使用浏览器捕获的短信请求，缺少发送记录仍拒绝，独占标记仍限制每个请求文件只调用一次短信接口。
- 手动工作流已接入 requests 的发送参数，以接口脚本的实际结果判断成功；默认仍只保存二维码。
- TDD 第一轮绿灯：提交 53d3987 的远端测试 https://github.com/C0verSnow/checkin/actions/runs/37948787298 ，12 个测试全部通过。
- PR #4 已关闭，已创建新的草稿 PR #5：https://github.com/C0verSnow/checkin/pull/5 。
- 真实流程 https://github.com/C0verSnow/checkin/actions/runs/37948809559 已保存接口二维码，但浏览器截图扫描未识别二维码，因此没有填写号码或发送短信。PNG 和报告已下载到本地被忽略的 output/issue-3-real/。
- 排查方向依次为：扫描标签漏掉二维码、尺寸或层级筛选排除了二维码、裁剪坐标偏移。远端真实流程较慢且依赖网站，先用浏览器入口的 SVG 二维码场景补充稳定复现，不在本地运行。
- 已添加第二个测试：可见 SVG 二维码也应允许登录流程继续准备 +86 表单，不发送短信。
- 本次重新读取 issue #3：最新正文只要求 requests 保存登录二维码，已不要求真实短信发送；后续真实验证不发送短信。
- 第二轮红灯已确认：提交 42f1f13 的远端测试 https://github.com/C0verSnow/checkin/actions/runs/37949798873 ，SVG 二维码场景失败，其余 12 个测试通过。
- 已沿用此前确认的浏览器登录入口和 requests 接口入口两个测试范围；没有新增测试范围。
- 已做最小修复：二维码候选扫描加入 SVG，仍以真实截图可解码为准。
- 修复已提交并推送到 feature 分支，提交为 d405362；README 已明确最新 issue 的默认二维码流程和 PNG/Python 附件。
- 已启动不发送短信的真实验证 https://github.com/C0verSnow/checkin/actions/runs/37950918119 ，先运行完整测试，再用 requests 调用真实二维码接口。
- 本次 Python 静态语法检查和 git diff --check 通过；没有运行本地项目代码或测试。
- 第二轮绿灯已确认：提交 d405362 的远端测试 https://github.com/C0verSnow/checkin/actions/runs/37950819334 ，13 个测试全部通过。
- 文档提交 e5d04ef 的 PR 测试 https://github.com/C0verSnow/checkin/actions/runs/37951146446 同样通过。
- 不发送短信的真实流程 https://github.com/C0verSnow/checkin/actions/runs/37950918119 已成功；requests 二维码接口返回 HTTP 200，真实二维码可解码，报告为 qr_saved=true、sms_attempted=false、status=not_requested。
- 已下载真实 PNG 和 Python 附件到被忽略的 output/issue-3-real-37950918119/，已查看接口二维码和结果 PNG。
- 如实记录剩余限制：浏览器已保存二维码并捕获请求，随后填写手机号时报输入内容不一致；独立 requests 二维码流程成功，最新 issue 不要求短信模式通过。
- PR #5 已按最终二维码流程重写标题和描述，并从草稿改为可审阅：https://github.com/C0verSnow/checkin/pull/5 。
- issue #3 已按最新二维码验收要求关闭，原因为已完成：https://github.com/C0verSnow/checkin/issues/3 。

## 没做：
- 没有进行本地构建、编译或运行测试。
- 本次真实流程没有发送短信；没有合并 PR。
- 没有修复真实网站的手机号输入问题；它不影响已捕获请求的 requests 二维码产出，最新 issue 不要求短信模式通过。

## 在做：
- 没有待完成的功能修改；最后提交 README 验证证据和本任务记录。

# Resume Studio Skill

一个面向 Codex 的通用简历生成技能。它把真实经历、项目资料和岗位 JD 转成可核验、可投递的简历版本，并提供 Markdown 工作区、事实审计、响应式 HTML 和 A4 PDF 导出。

核心原则是 **美化表达，不虚构事实**。项目、时间、身份、证书、职责和数字都必须能追溯到原始资料。

## 功能

- 为不同岗位方向生成有实质差异的简历版本。
- 将“做过什么”改写为问题、行动、方法和验证结果。
- 按 JD 重排项目与技能，提高 ATS 和招聘者扫描效率。
- 检查占位符、联系方式来源、无依据数字、目标关键词和文档结构。
- 使用内置单栏模板生成 HTML 与可复制文字的 A4 PDF。
- 附带中英文写作、早期职业、转岗、证据分级和最终质检指南。

## 安装

将 `resume-studio` 文件夹复制到 Codex 的用户技能目录：

```text
%USERPROFILE%\.codex\skills\resume-studio
```

重新启动或新建 Codex 会话后，即可使用 `$resume-studio`。

也可以在支持 Python 的终端中直接调用脚本，不需要先安装为 Codex 技能。

## 快速开始

```bash
python resume-studio/scripts/resume_tool.py init ./resume-work \
  --name "Candidate Name"
```

填写：

- `resume-work/profile.md`：真实经历和联系方式。
- `resume-work/evidence.md`：证据、冲突和待确认事项。
- `resume-work/targets/<方向>/jd.md`：目标岗位 JD。
- `resume-work/targets/<方向>/brief.json`：方向、页数和关键词。

完成简历后执行事实审计：

```bash
python resume-studio/scripts/resume_tool.py audit \
  resume-work/output/example/resume.md \
  --source resume-work/profile.md \
  --source resume-work/evidence.md \
  --brief resume-work/targets/example/brief.json
```

生成 HTML 和 PDF：

```bash
python resume-studio/scripts/resume_tool.py render \
  resume-work/output/example/resume.md \
  --out-dir resume-work/output/example \
  --title "Candidate Name — Target Role" \
  --lang zh-CN
```

## 依赖

- Python 3.10 或更高版本。
- PDF 导出需要本机安装 Chrome、Edge、Chromium 或 Brave；脚本只使用 Python 标准库。
- 没有 Chromium 浏览器时仍会输出可直接打印为 PDF 的 HTML。

## 隐私

本仓库只包含技能代码、空白工作区模板和虚构示例，不包含任何真实求职者资料。使用者应自行保管 `profile.md`、原始证书、项目资料和生成后的简历。

## 目录

```text
resume-studio/
├── SKILL.md
├── agents/openai.yaml
├── assets/
├── references/
└── scripts/resume_tool.py
```

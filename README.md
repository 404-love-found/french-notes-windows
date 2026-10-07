# Windows 法语笔记

![Windows build](https://github.com/404-love-found/french-notes-windows/actions/workflows/windows.yml/badge.svg)

这是一个全法语界面的本机桌面工具。每行输入一个法语单词或一句话，完成输入后与当前 CSV 对比，只录入尚未保存的内容。所有笔记保存在 CSV 文件中，可按单词、句子分组导出为 Word `.docx`。

## 在 Windows 上使用

在 [Releases 下载页](https://github.com/404-love-found/french-notes-windows/releases/latest) 获取 Windows 64 位版本：

- **安装版：**下载 `FrenchNotes-Setup-0.1.4.exe`，双击安装后从开始菜单或桌面快捷方式启动。
- **免安装版：**下载 `FrenchNotes-0.1.4-Windows-x64.zip`，解压后双击 `FrenchNotes.exe`。

这两个版本均已包含 Python 和 Word 导出依赖。录入、查阅、去重和导出均可离线进行，不需要在电脑上安装 Python 或 Word。数据位于当前用户的本机应用数据目录；卸载程序不会删除 CSV 笔记。

### 从源码运行

1. 安装 [Python](https://www.python.org/downloads/windows/) 3.11 或更新版本，包含默认的 Tcl/Tk 和 Python Launcher。
2. 把项目解压到一个本机文件夹。
3. 首次双击 `setup_windows.bat` 安装导出依赖，需要联网下载一次。
4. 双击 `start_windows.bat` 打开应用。此后记笔记、读取 CSV 和导出 Word 都不需要联网。

导出操作不需要安装 Word。查看和编辑导出的 `.docx` 可使用 Word 或其他兼容软件。

### 操作流程

1. 在「Saisie par lot」中输入或粘贴多行法语，每个非空行是一条笔记。
2. 点击「Analyser」，查看每条内容的分类和结果。
3. 若分类不合适，选中新增项，点击「Mot」或「Phrase」。可以多选。
4. 点击「Enregistrer les nouvelles notes」，只把新增项保存到当前 CSV。保存成功后输入区清空；失败时保留输入。
5. 在「Notes enregistrées」中搜索、按分类筛选、双击查看全文。
6. 点击「Tout exporter vers Word」，选择本机 `.docx` 路径。导出包含当前 CSV 的所有笔记，不受列表搜索或筛选影响，也不包含未保存的输入。

输入期间不会修改 CSV。全部输入都已存在时，应用显示「Aucune nouvelle note」，不写入 CSV。再次打开应用会读取同一份 CSV。

## 已确认的比较规则

比较键按顺序进行 Unicode NFC 规范化、去除首尾空白、合并连续空白、忽略大小写。笔记内容保留大小写、法语重音和标点，首尾及连续空白整理后保存。

| 两条输入 | 判断 |
| --- | --- |
| `Bonjour` 和 ` bonjour ` | 重复 |
| `Je suis étudiant.` 和 `JE  SUIS étudiant.` | 重复 |
| `école` 和 `ecole` | 不同，重音保留 |
| `a` 和 `à` | 不同 |
| `Bonjour` 和 `Bonjour !` | 不同，标点保留 |
| `l'homme` 和 `l’homme` | 不同，直撇号与弯撇号属于标点差异 |

比较以法语内容为准，不因分类不同重复录入。CSV 已有项跳过；本批重复项只保留第一次。点击保存时再读取最新 CSV 并重新去重，因此预览后由其他实例加入的相同内容也会跳过。已有笔记不会被本批重新分类。

## 分类规则与边界

第一版采用离线规则分类，不调用在线服务。

- 一个无空格、无句子标点的书写词默认归为「单词」；内部撇号和连字符可保留，例如 `aujourd’hui`、`arc-en-ciel`。
- 多词内容或含句子标点的内容默认归为「句子」，例如 `Je suis étudiant.`、`Bonjour !`。
- 空行忽略；不含字母的内容会提示修正，不会悄悄录入。

这是可修正的自动建议，无法准确区分所有固定词组、缩写和省略句。例如 `pomme de terre` 会先归为句子，可在预览中改为单词；`M.`、`j’aime` 也可能需要修正。当前不提供翻译、语法分析或自动补充释义。

## 本机文件

Windows 默认保存路径：

```text
%LOCALAPPDATA%\FrenchNotes\notes.csv
```

应用顶部显示当前路径。「Choisir un CSV」可切换到同格式的已有 CSV，或指定一个尚未存在的新文件。「Ouvrir le dossier」可查看本机文件。为了保持数据仅在本机，选择文件时应使用本机文件夹；若自行放在 OneDrive 等同步目录中，同步由该软件控制。

CSV 使用 UTF-8 BOM 和标准 CSV 引号规则，支持法语重音、中文、逗号、引号及字段内换行。字段为：

| 字段 | 用途 |
| --- | --- |
| `id` | 每条记录的唯一 ID |
| `category` | `word`（单词）或 `sentence`（句子） |
| `french` | 法语内容 |
| `created_at` | 录入时间，ISO 格式 |

CSV 首行必须是 `id,category,french,created_at`。其他格式会提示错误并保留原文件。尚未选择任何现有文件时，第一次保存会自动创建 CSV；不预填示例数据。

保存采用同目录临时文件写入并替换，上一版数据保存在 `notes.csv.bak`。备份只有上一版，长期保存可另行复制 CSV。零新增时不更新文件或备份。

保存时通过 `.lock` 文件阻止本应用多个实例同时写入，并检查外部修改。若崩溃留下锁文件，先关闭所有本应用实例，确认没有正在保存的任务，再手动删除对应 `notes.csv.lock`。使用 Excel 等软件编辑 CSV 时，应先关闭应用，保存并关闭 CSV 后重新打开应用；文件操作无法替代跨软件的完整并发控制。

`settings.json` 仅保存所选 CSV 的路径，位于默认应用数据文件夹，不存笔记内容。Word 导出到你选择的位置；若文件正在被 Word 占用，关闭文档后重试。

## 制作 Windows 可执行文件

在 Windows 中先完成首次安装，再双击 `build_windows.bat`。生成 `dist\FrenchNotes.exe` 后，可复制这个文件使用，目标电脑无需安装 Python。

也可以在 Windows PowerShell 中执行 `packaging/build_windows.ps1`，生成安装版、免安装版及 SHA-256 校验文件。构建必须在 Windows 环境执行，参见 [PyInstaller 官方说明](https://pyinstaller.org/en/v6.16.0/operating-mode.html)。

GitHub Actions 在 Windows 环境运行完整测试，并在发布前执行打包后的 `FrenchNotes.exe --self-test NEW_DIRECTORY`，检查实际可执行文件的 Tk 界面初始化、CSV 去重和 Word 导出。自检路径必须是尚未存在的新目录，自检不会访问已有笔记。

推送 `v*` 版本标签后，工作流把通过验证的产物发布到 GitHub Releases。普通代码推送和手动运行产生的下载包可在对应 Actions 运行页面获取。

## 开发验证

```bash
python -m unittest discover -s tests -v
python -m french_notes
```

UI 测试需要可用的桌面显示环境和 Tk；核心 CSV 测试可独立运行。Word 测试需要安装 `requirements.txt`。

测试覆盖比较规则、CSV 安全保存、分类修正、界面录入流程、打包自检和 Word 导出。示例 Word 已渲染并检查法语标题、重音和长句换行。Windows 构建结果以本仓库 Actions 状态为准。

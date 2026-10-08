# Windows 法语笔记

[下载 Windows 0.2.0](https://github.com/404-love-found/french-notes-windows/releases/tag/v0.2.0)

![Windows build](https://github.com/404-love-found/french-notes-windows/actions/workflows/windows.yml/badge.svg)

FrenchNotes 0.2.0 是一个本机桌面工具，界面支持中文、English、Français 即时切换并记住选择，首次启动默认法语。每行输入一个法语单词或一句话，完成输入后与当前 CSV 对比，只录入尚未保存的内容。所有笔记累计保存在 CSV 文件中，可按单词、句子分组导出为 Word `.docx`。

界面采用输入和已保存笔记两个页签，底部显示 `ZIRELTON TECHNOLOGIES INC.`。该标识不写入 CSV 或导出的 Word 文档。

## 在 Windows 上使用

在上面的 0.2.0 下载页获取 Windows 10 / 11 的 64 位（x64）版本：

- **安装版：**下载 [FrenchNotes-Setup-0.2.0.exe](https://github.com/404-love-found/french-notes-windows/releases/download/v0.2.0/FrenchNotes-Setup-0.2.0.exe)，双击安装后从开始菜单或桌面快捷方式启动。
- **免安装版：**下载 [FrenchNotes-0.2.0-Windows-x64.zip](https://github.com/404-love-found/french-notes-windows/releases/download/v0.2.0/FrenchNotes-0.2.0-Windows-x64.zip)，解压后双击 `FrenchNotes.exe`，保留随附的 `licenses` 文件夹。

这两个版本均包含 Python 和 Word 导出依赖。录入、查阅、去重和导出均可离线进行，不需要在电脑上安装 Python 或 Word。数据位于当前用户的本机应用数据目录；升级和卸载程序不会删除 CSV 笔记。

安装向导提供 Français 和 English；官方 Inno Setup 编译器包带有简体中文语言文件时，也会提供中文向导。安装器语言与应用界面语言分别设置：应用始终提供三种语言，可在窗口顶部选择。程序与安装包暂未数字签名。

### 从源码运行

1. 安装 [Python](https://www.python.org/downloads/windows/) 3.11 或更新版本，包含默认的 Tcl/Tk 和 Python Launcher。
2. 把项目解压到一个本机文件夹。
3. 首次双击 `setup_windows.bat` 安装导出依赖，需要联网下载一次。
4. 双击 `start_windows.bat` 打开应用。此后记笔记、读取 CSV 和导出 Word 都不需要联网。

导出操作不需要安装 Word。查看和编辑导出的 `.docx` 可使用 Word 或其他兼容软件。

### 操作流程

以下使用默认法语界面的按钮名称；切换语言不会翻译笔记正文，也不会清空当前输入或已保存笔记。

1. 在「Saisie par lot」中输入或粘贴多行法语，每个非空行是一条笔记。
2. 点击「Analyser」，查看每条内容的分类和结果。
3. 若分类不合适，选中新增项，点击「Mot」或「Phrase」。可以多选。
4. 点击「Enregistrer les nouvelles notes」，只把新增项保存到当前 CSV。保存成功后输入区清空；失败时保留输入。
5. 在「Notes enregistrées」中搜索、按分类筛选、双击查看全文。
6. 点击「Exporter Word」，选择本机 `.docx` 路径。导出包含当前 CSV 的所有笔记，不受列表搜索或筛选影响，也不包含未保存的输入。标题、单词/句子分类和说明跟随当前界面语言，已保存笔记正文保持原样。

输入期间不会修改 CSV。全部输入都已存在时，应用显示「Aucune nouvelle note」，不写入 CSV。再次打开应用会读取同一份 CSV，并恢复上次选择的界面语言。

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

应用采用离线规则分类，不调用在线服务。

- 一个无空格、无句子标点的书写词默认归为「单词」；内部撇号和连字符可保留，例如 `aujourd’hui`、`arc-en-ciel`。
- 多词内容或含句子标点的内容默认归为「句子」，例如 `Je suis étudiant.`、`Bonjour !`。
- 空行忽略；不含字母的内容会提示修正，不会悄悄录入。

这是可修正的自动建议，无法准确区分所有固定词组、缩写和省略句。例如 `pomme de terre` 会先归为句子，可在预览中改为单词；`M.`、`j’aime` 也可能需要修正。当前不提供翻译、语法分析或自动补充释义。

## 本机文件

Windows 默认保存路径：

```text
%LOCALAPPDATA%\FrenchNotes\notes.csv
```

应用顶部显示当前路径。「Choisir un CSV」可切换到同格式的已有 CSV，或指定一个尚未存在的新文件。切换 CSV 不会删除原库、其他 CSV 或备份；当前输入会保留，需针对新选择的 CSV 重新分析。「Ouvrir le dossier」可查看当前 CSV 所在文件夹。为了保持数据仅在本机，选择文件时应使用本机文件夹；若自行放在 OneDrive 等同步目录中，同步由该软件控制。

CSV 使用 UTF-8 BOM 和标准 CSV 引号规则，支持法语重音、中文、逗号、引号及字段内换行。字段为：

| 字段 | 用途 |
| --- | --- |
| `id` | 每条记录的唯一 ID |
| `category` | `word`（单词）或 `sentence`（句子） |
| `french` | 法语内容 |
| `created_at` | 录入时间，ISO 格式 |

CSV 首行必须是 `id,category,french,created_at`。其他格式会提示错误并保留原文件。尚未选择任何现有文件时，第一次保存会自动创建 CSV；不预填示例数据。

保存会把历史记录与独特新增项合并，先写入同目录临时文件，再原子替换当前 CSV。新一批输入不会覆盖历史笔记。从 0.2.0 起，不再生成 `.bak` 备份；只有新增记录成功写入后，才清理当前 CSV 对应的旧 `.bak`，例如 `notes.csv.bak`，不会清理其他数据文件。

零新增时不重写 CSV，也不清理旧 `.bak`。CSV 替换失败时保留原 CSV 和旧备份；若写入已成功但清理旧备份或锁文件失败，应用会提示已保存并保留成功结果。长期备份请自行复制 CSV。

保存时通过 `.lock` 文件阻止本应用多个实例同时写入，并检查外部修改。若崩溃留下锁文件，先关闭所有本应用实例，确认没有正在保存的任务，再手动删除对应 `notes.csv.lock`。使用 Excel 等软件编辑 CSV 时，应先关闭应用，保存并关闭 CSV 后重新打开应用；文件操作无法替代跨软件的完整并发控制。

`settings.json` 保存所选 CSV 的路径和界面语言，位于默认应用数据文件夹，不存笔记内容。Word 导出到你选择的位置；若文件正在被 Word 占用，关闭文档后重试。

## 制作 Windows 可执行文件

在 Windows 中先完成首次安装，再双击 `build_windows.bat`。生成 `dist\FrenchNotes.exe` 后，可复制这个文件使用，目标电脑无需安装 Python。

完整分发包使用 Windows PowerShell 构建。先安装官方 Inno Setup 6，再运行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File packaging\build_windows.ps1 -Python ".venv\Scripts\python.exe" -BuildInstaller
```

生成安装版、免安装版及 SHA-256 校验文件。不加 `-BuildInstaller` 时只生成独立 EXE、免安装 ZIP 和校验文件；已有 Chocolatey 的构建机器可增加 `-InstallInnoSetup` 安装脚本指定版本。构建必须在 Windows 环境执行，参见 [PyInstaller 官方说明](https://pyinstaller.org/en/v6.16.0/operating-mode.html)。

GitHub Actions 在 Windows 环境运行完整测试，并在发布前执行打包后的 `FrenchNotes.exe --self-test NEW_DIRECTORY`，检查实际可执行文件的 Tk 界面初始化、CSV 去重和 Word 导出。自检路径必须是尚未存在的新目录，自检不会访问已有笔记。

推送 `v*` 版本标签后，工作流把通过验证的产物发布到 GitHub Releases。普通代码推送和手动运行产生的下载包可在对应 Actions 运行页面获取。

## 开发验证

```bash
python -m unittest discover -s tests -v
python -m french_notes
```

UI 测试需要可用的桌面显示环境和 Tk；核心 CSV 测试可独立运行。Word 测试需要安装 `requirements.txt`。

测试覆盖比较规则、CSV 安全累积保存、旧备份清理边界、分类修正、界面录入与语言切换、按钮布局、打包自检和 Word 导出。Windows 构建结果以本仓库 Actions 状态为准。

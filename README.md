# kartemu

一个 **3D 卡丁车模拟器**(kart 风格竞速)的可驾驶原型与配套资产工具链:
three.js 渲染 + 自研物理,含 1 条赛道、1 台赛车、1 个卡通角色(骨架蒙皮 +
官方级动画回放)。本仓库同时完整记录了从闭源 H5 客户端到独立可运行原型的
格式逆向、渲染管线分析工程过程。

> 仅用于学习研究。

## 快速开始

```bash
python server.py        # http://127.0.0.1:8088/
# 驾驶原型: http://127.0.0.1:8088/web/index.html
# 角色查看器: http://127.0.0.1:8088/web/character.html
# 操作: W/↑ 油门  S/↓ 刹车  A/D 转向  空格 漂移  R 回到起点
```

资产生成(需要本地已解包的游戏数据,格式细节见 FORMATS.md):

```bash
python rho_unpack.py theme_xyy.rho    # 容器解包 -> unpacked/
python s1_gltf.py unpacked/track_village_R01/track.1s web/track track
python s1_gltf.py unpacked/DataPack2_00007/kart_/cotton1/model.1s web/kart kart --model
python char_gltf.py unpacked/character_dao/model.1s web/character dao   # 骨骼蒙皮+动画
```

## 目录结构

| 路径 | 说明 |
|---|---|
| `web/index.html` | three.js 驾驶原型(赛道+赛车+角色) |
| `web/character.html` | 角色单独查看器(骨架蒙皮 + 32 段动画切换) |
| `web/track|kart|character/` | 导出的 glTF 资产(不入库) |
| `rho_unpack.py` / `rho5_unpack.py` | 游戏资源容器解包器 |
| `s1_parse.py` / `s1_gltf.py` | 场景对象图解析器 / glTF 导出器 |
| `char_gltf.py` / `char_pose.py` / `pose_eval.py` | 角色骨骼蒙皮导出 / 动画求值与数值验证 |
| `extract_fn.py` / `rename_pass.py` / `deobfuscate.py` | 代码分析工具(函数提取/重命名/去混淆) |
| `extract_kartspec.py` | 车辆物理参数表提取(92+74 参数) |
| `server.py` / `downloader.py` | 本地静态服务 / 站点镜像下载 |
| `SYMBOLS.md` | 客户端 bundle 1673 个符号 + 106 个类的全量索引 |
| `UNDERSTOOD.md` | 深度逆向笔记(坐标系/渲染/物理/路线/动画,§1-21) |
| `FORMATS.md` | 容器与模型/动画文件格式细节 |
| `PROJECT_MEMORY.md` | 跨会话项目记忆(规则/状态/结论速查) |

## 当前进度

- ✅ 资源容器与模型/动画格式逆向 + 解包器,全部校验通过
- ✅ 客户端 bundle 完整反编译:字符串 100% 内联、语义重命名、符号索引
- ✅ 坐标系三空间(数据 Z-up / 物理 Y-up / 呈现)语义彻底吃透
- ✅ 导出器对齐官方渲染语义:UV 原样、strip 奇偶展开、cull→side、det 翻面、
  顶点色、alphaTest、unlit —— 赛道观感与原版一致
- ✅ 赛车 + 角色上车可见,转向方向校准
- ✅ 角色:骨骼蒙皮 glTF(24 骨骼 + 32 段动画剪辑)、脸/身体贴图合成、
  刚性件挂骨骼,全链数值闭环(与官方求值逐顶点偏差 ≤ 4e-5)
- ⏳ 碰撞重做(网格 rayQuery + 墙障碍)
- ⏳ 漂移手感对齐全部物理参数、检查点/圈数判定

## 法律说明

本仓库只包含自研工具、文档与原型代码。任何来自原客户端的资源、解包产物、
反编译代码及提取数据均被 .gitignore 排除,不入库、不分发。

## 维护备注

- 推送:直连 github.com 超时,用 `git -c http.proxy=http://127.0.0.1:7892 push origin main`。
- 严禁提交原客户端资产(见 .gitignore 清单);git 历史已做过一次全量大文件清洗,勿再引入。
- 自制工具必须全部开源入库,不得只发布打包产物。

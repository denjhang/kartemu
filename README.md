# kartemu

一个 **3D 卡丁车模拟器**(kart 风格竞速)的可驾驶原型与配套资产工具链:
three.js 渲染 + 自研物理,含 1 条赛道、1 台赛车、1 个卡通角色(骨架蒙皮 +
官方级动画回放)。本仓库同时完整记录了从闭源 H5 客户端到独立可运行原型的
格式逆向、渲染管线分析工程过程。

> 仅用于学习研究。

## 快速开始

```bash
python tools/server.py    # http://127.0.0.1:8088/
# 驾驶原型: http://127.0.0.1:8088/web/index.html
# 角色查看器: http://127.0.0.1:8088/web/character.html
# 操作: W/↑ 油门  S/↓ 刹车  A/D 转向  空格 漂移  R 回到起点
```

资产生成(在项目根目录运行,需要本地已解包的游戏数据,格式细节见 docs/FORMATS.md):

```bash
python tools/rho_unpack.py theme_xyy.rho    # 容器解包 -> unpacked/
python tools/s1_gltf.py unpacked/track_village_R01/track.1s web/track track
python tools/s1_gltf.py unpacked/DataPack2_00007/kart_/cotton1/model.1s web/kart kart --model
python tools/char_gltf.py unpacked/character_dao/model.1s web/character dao   # 骨骼蒙皮+动画
```

## 目录结构

```
kartemu/
├── web/                    # three.js 前端(驾驶原型 + 角色查看器 + 导出资产)
├── tools/                  # 自研工具链(全部开源)
│   ├── rho_unpack.py       #   资源容器解包器(.rho)
│   ├── rho5_unpack.py      #   资源容器解包器(.rho5)
│   ├── s1_parse.py         #   场景对象图解析器(.1s)
│   ├── s1_gltf.py          #   场景/车辆 → glTF 导出器
│   ├── char_gltf.py        #   角色 → 骨骼蒙皮 glTF + 动画剪辑导出器
│   ├── char_pose.py        #   角色动画求值(采样/骨骼链/蒙皮)
│   ├── pose_eval.py        #   动画管线数值验证脚本
│   ├── deobfuscate.py      #   客户端 bundle 去混淆(字符串还原)
│   ├── extract_fn.py       #   按函数粒度提取 bundle 代码
│   ├── rename_pass.py      #   符号语义重命名
│   ├── extract_kartspec.py #   车辆物理参数表提取(92+74 参数)
│   ├── build_kit.py        #   工具链打包
│   ├── downloader.py       #   站点镜像下载
│   └── server.py           #   本地静态服务(含 /web/ 路由)
├── docs/                   # 逆向研究与工程文档
│   ├── UNDERSTOOD.md       #   深度逆向笔记(坐标系/渲染/物理/路线/动画,§1-21)
│   ├── FORMATS.md          #   容器与模型/动画文件格式细节
│   ├── SYMBOLS.md          #   客户端 bundle 1673 符号 + 106 类全量索引
│   └── PROJECT_MEMORY.md   #   跨会话项目记忆(规则/状态/结论速查)
└── README.md
```

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

# kartemu

跑跑卡丁车(KartRider)民间 H5 复刻版 **KartSim**(https://kart.iii.moe/) 的逆向研究与
自制克隆。目标:脱离官方 .rho 资源包,用解包后的独立资产实现 1 条赛道(城镇高速公路)、
1 台赛车(板车 cotton1)、1 个角色(皮蛋 Dao)的可驾驶原型。

> 仅用于学习研究。官方资源(.rho/.rho5/.1s/贴图/模型)与反编译产物均不入库。

## 快速开始

```bash
python server.py        # http://127.0.0.1:8088/
# 原型: http://127.0.0.1:8088/web/index.html
# 操作: W/↑ 油门  S/↓ 刹车  A/D 转向  空格 漂移  R 回到起点
```

资产生成(需要先有解包产物,见 FORMATS.md):

```bash
python rho_unpack.py theme_xyy.rho    # 解包官方容器 -> unpacked/
python s1_gltf.py unpacked/track_village_R01/track.1s web/track track
python s1_gltf.py unpacked/DataPack2_00007/kart_/cotton1/model.1s web/kart kart --model
python s1_gltf.py unpacked/character_dao/model.1s web/character dao --model
```

## 目录结构

| 路径 | 说明 |
|---|---|
| `web/index.html` | three.js 驾驶原型(赛道+板车+皮蛋) |
| `web/track|kart|character/` | 导出的 glTF 资产(不入库) |
| `rho_unpack.py` / `rho5_unpack.py` | .rho / .rho5 容器解包器 |
| `s1_parse.py` / `s1_gltf.py` | .1s 对象图解析器 / glTF 导出器 |
| `extract_fn.py` / `rename_pass.py` | 主 bundle 函数提取 / 语义重命名 |
| `extract_kartspec.py` | 官方车辆物理参数表提取(92+74 参数) |
| `server.py` / `downloader.py` | 本地镜像服务 / 站点镜像下载 |
| `SYMBOLS.md` | 主 bundle 1673 个符号 + 106 个类的全量索引 |
| `UNDERSTOOD.md` | 深度逆向笔记(坐标系/渲染/物理/路线/动画) |
| `FORMATS.md` | .rho/.rho5/.1s 等格式细节 |

## 当前进度

- ✅ 三大资源格式逆向 + 解包器(.rho / .rho5 / .1s),全部校验通过
- ✅ KartSim 主 bundle 完整反编译:字符串 100% 内联、语义重命名、符号索引
- ✅ 坐标系三空间(D 数据 Z-up / P 物理 Y-up / 呈现)与 l1/ae/u1 语义彻底吃透
- ✅ 导出器对齐官方渲染语义:UV 原样、strip 奇偶展开、cull→side、det 翻面、
  顶点色、官方 alphaTest、unlit —— 城镇高速观感与官方一致
- ✅ 板车 cotton1 + 皮蛋上车可见
- ⏳ 人物调色板(characterColorIds/palette)→ 皮蛋体色
- ⏳ 转向符号校准(官方 integrateStandardOrientation)、碰撞(Z$ 网格+墙)重做
- ⏳ 漂移手感对齐 kartspec 全参数、检查点/圈数(ToRoad gate)

## 法律说明

本仓库只包含自研工具、文档与原型代码。KartSim 官方资源(mirror/、unpacked/)、
反编译产物(deob_*.js、study_*.js、string_table.json)、从官方客户端提取的数据
(kartspec.csv)及导出资产(web/track 等)全部被 .gitignore 排除,不得分发。

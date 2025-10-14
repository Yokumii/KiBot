import datetime
import io
import os
import platform
from enum import Enum
from pathlib import Path
from typing import Tuple, List, Dict

import numpy as np
from PIL import Image
from matplotlib import font_manager as fm
from matplotlib import lines as mpl_lines
from matplotlib import patches as mpl_patches
from matplotlib import pyplot as plt
from metpy.plots.mapping import ccrs

from .models import StormResponse

STORM_TYPE_COLORS = {
    'TD': '#00E400',  # 热带低压 绿色
    'TS': '#FFFF00',  # 热带风暴 黄色
    'STS': '#FF8C00',  # 强热带风暴 橙色
    'TY': '#FF0000',  # 台风 红色
    'STY': '#FF00FF',  # 强台风 紫色
    'SuperTY': '#800080'  # 超强台风 深紫色
}

STORM_TYPE_CN = {
    'TD': '热带低压',
    'TS': '热带风暴',
    'STS': '强热带风暴',
    'TY': '台风',
    'STY': '强台风',
    'SuperTY': '超强台风'
}

DIR_DEG = {
        'N': 0, 'NNE': 22.5, 'NE': 45, 'ENE': 67.5,
        'E': 90, 'ESE': 112.5, 'SE': 135, 'SSE': 157.5,
        'S': 180, 'SSW': 202.5, 'SW': 225, 'WSW': 247.5,
        'W': 270, 'WNW': 292.5, 'NW': 315, 'NNW': 337.5
}


class TyphoonScope(Enum):
    SMALL = "small"
    LARGE = "large"


class TyphoonRenderer:
    def __init__(self):
        cur_dir = os.path.dirname(__file__)
        self.base_image: np.ndarray = plt.imread(os.path.join(cur_dir, 'resources', 'ne_base.png'))
        self.base_image_large: np.ndarray = plt.imread(os.path.join(cur_dir, 'resources', 'ne_base_large.png'))
        self.extent: Tuple[float, float, float, float] = (105, 140, 15, 50)  # lon_min, lon_max, lat_min, lat_max
        self.extent_large: Tuple[float, float, float, float] = (100, 160, 5, 50)
        self.proj = ccrs.PlateCarree()  # 设置投影
        self.aspect = (self.extent[1] - self.extent[0]) / (self.extent[3] - self.extent[2])
        self.aspect_large = ((self.extent_large[1] - self.extent_large[0]) /
                             (self.extent_large[3] - self.extent_large[2]))
        self.dpi = 800

    def render(self, storm_data: List[StormResponse]) -> Image:
        self._set_font()

        typhoon_scope = self._choose_scope(storm_data)

        h = 8
        w = h * (self.aspect if typhoon_scope == TyphoonScope.SMALL else self.aspect_large)

        fig, ax = plt.subplots(
            figsize=(w, h),
            dpi=self.dpi,
            subplot_kw={'projection': self.proj},
        )

        ax.imshow(
            self.base_image if typhoon_scope == TyphoonScope.SMALL else self.base_image_large,
            origin='upper',
            extent=self.extent if typhoon_scope == TyphoonScope.SMALL else self.extent_large,
            transform=self.proj,
            zorder=0,
        )

        storm_data = self._filter_data_by_scope(storm_data, typhoon_scope)

        gl = ax.gridlines(
            draw_labels=True,
            linewidth=0.5,
            color='gray',
            alpha=0.8,
            linestyle='--',
            zorder=1,
        )

        gl.top_labels = False
        gl.xlabel_style = {'size': 8, 'color': 'gray'}
        gl.ylabel_style = {'size': 8, 'color': 'gray'}

        self._draw_track_line(ax, storm_data)
        self._draw_history_points(ax, storm_data)
        self._draw_latest_point(ax, storm_data)

        self._draw_legend(ax, typhoon_scope)

        self._draw_title(ax, storm_data)
        self._draw_footer(ax)

        # 将图像输出至缓冲区
        buffer = io.BytesIO()
        fig.savefig(buffer, format='png', dpi=self.dpi, bbox_inches='tight', pad_inches=0.1)
        plt.close(fig)
        buffer.seek(0)

        img_origin = Image.open(buffer)
        img_copy = img_origin.copy()
        buffer.close()

        return img_copy

    def render_to_file(self, storm_data: List[StormResponse], output_path: str) -> bool:
        # noinspection PyBroadException
        try:
            output = Path(output_path)
            output.parent.mkdir(parents=True, exist_ok=True)

            typhoon_img: Image.Image = self.render(storm_data)
            typhoon_img.save(output)
            return True
        except Exception as e:
            print(e)
            return False

    def _choose_scope(self, storm_data: List[StormResponse]) -> TyphoonScope:
        """
            根据台风路径信息决定是否使用大画幅。
            最新数据在小画幅内，则使用小画幅
            如果任意一个路径点落在小画幅范围之外，则返回大画幅。
        """
        lon_min, lon_max, lat_min, lat_max = self.extent

        if not storm_data:
            return TyphoonScope.SMALL

        latest = storm_data[0]
        lat = float(latest.stormInfo.lat)
        lon = float(latest.stormInfo.lon)

        if lat_min <= lat <= lat_max and lon_min <= lon <= lon_max:
            return TyphoonScope.SMALL

        for data in storm_data:
            lat = float(data.stormInfo.lat)
            lon = float(data.stormInfo.lon)

            # 如果有任何一个点不在小画幅范围内，返回大画幅
            if not (lat_min <= lat <= lat_max and lon_min <= lon <= lon_max):
                return TyphoonScope.LARGE

        return TyphoonScope.SMALL

    def _filter_data_by_scope(self, storm_data: List[StormResponse], scope: TyphoonScope) -> List[StormResponse]:
        """
        根据选定的画幅筛选数据：
        只保留落在对应画幅范围内的路径点。
        """
        if scope == TyphoonScope.SMALL:
            lon_min, lon_max, lat_min, lat_max = self.extent
        else:  # LARGE
            lon_min, lon_max, lat_min, lat_max = self.extent_large

        filtered: List[StormResponse] = []
        for data in storm_data:
            lat = float(data.stormInfo.lat)
            lon = float(data.stormInfo.lon)
            if lat_min <= lat <= lat_max and lon_min <= lon <= lon_max:
                filtered.append(data)

        return filtered

    def _draw_track_line(self, ax: plt.Axes, storm_data: List[StormResponse]) -> None:
        """
            绘制台风路径线
            默认storm_data按时间倒序排列，最新一条在索引0
        """
        if len(storm_data) < 2:
            return  # 单独一个点的数据无需绘制路径

        lons = [float(p.stormInfo.lon) for p in reversed(storm_data)]
        lats = [float(p.stormInfo.lat) for p in reversed(storm_data)]

        ax.plot(
            lons, lats,
            color='#555555',
            linewidth=1.0,
            transform=self.proj,
            zorder=2,
        )

    def _draw_history_points(self, ax: plt.Axes, storm_data: List[StormResponse]) -> None:
        """
        绘制历史台风点位（不含最新点）
        """
        if len(storm_data) <= 1:
            return

        for p in storm_data[:0:-1]:
            lon = float(p.stormInfo.lon)
            lat = float(p.stormInfo.lat)
            color = STORM_TYPE_COLORS[p.stormInfo.type]

            ax.scatter(lon, lat,
                       s=6 ** 2,
                       c=color,
                       edgecolors='white',
                       linewidths=0.5,
                       transform=self.proj,
                       zorder=3)

    def _draw_latest_point(self, ax: plt.Axes, storm_data: List[StormResponse]) -> None:
        """
            最新点绘制，包括风圈、移动方向、文字信息等
        """
        if not storm_data:
            return

        latest = storm_data[0]
        lon = float(latest.stormInfo.lon)
        lat = float(latest.stormInfo.lat)
        ty_type = latest.stormInfo.type
        color = STORM_TYPE_COLORS[ty_type]

        # 1.风圈
        km2deg = 1 / 111.0
        alpha = {'7': 0.15, '10': 0.25, '12': 0.35}
        radii_km = self._estimate_wind_radii(latest)
        for lvl, r_km in radii_km.items():
            r_deg = r_km * km2deg
            circle = mpl_patches.Circle(
                (lon, lat), r_deg,
                fc=color,
                ec='none',
                alpha=alpha[lvl],
                transform=self.proj,
                zorder=4,
            )
            ax.add_patch(circle)

        # 2.中心圆
        ax.scatter(
            lon, lat,
            s=8 ** 2,
            c=color,
            edgecolors='white',
            linewidths=0.6,
            transform=self.proj,
            zorder=5,
        )

        # 3.方向箭头
        spd = float(latest.stormInfo.moveSpeed)  # km/h
        if latest.stormInfo.move360.strip():
            dir360 = float(latest.stormInfo.move360)
        else:
            dir360 = DIR_DEG.get(latest.stormInfo.moveDir, 0)

        length = spd * 3.0 * km2deg  # 可调系数
        dx = length * np.sin(np.deg2rad(dir360))
        dy = length * np.cos(np.deg2rad(dir360))
        ax.arrow(lon, lat, dx, dy,
                 head_width=0.25,
                 head_length=0.18,
                 fc='white',
                 ec='black',
                 lw=0.6,
                 transform=self.proj,
                 zorder=6)

        # 4.文字标签
        cn_type = STORM_TYPE_CN[latest.stormInfo.type]
        txt = (f"{self._format_time(latest.stormInfo.pubTime)}  "
               f"{cn_type}  "
               f"{latest.stormInfo.windSpeed}m/s  "
               f"{latest.stormInfo.pressure}hPa")
        ax.text(lon + 0.5, lat + 0.5, txt,
                fontsize=7, color='black',
                bbox=dict(boxstyle='round,pad=0.3',
                          facecolor='white', alpha=0.85),
                transform=self.proj, zorder=7)

    @staticmethod
    def _draw_legend(ax: plt.Axes, scope: TyphoonScope) -> None:
        """
        在图幅空白处绘制
        1) 强度色标（圆形）
        2) 风圈示例
        """
        color_patches = []
        for code, cn in STORM_TYPE_CN.items():
            color_patches.append(
                mpl_lines.Line2D([], [], marker='o', color='w', markersize=8,
                                 markerfacecolor=STORM_TYPE_COLORS[code],
                                 markeredgecolor='k', linewidth=0,
                                 label=cn))

        wind_patch = mpl_lines.Line2D([], [], marker='o', color='gray', linewidth=0,
                                      markersize=8,
                                      markerfacecolor='none',
                                      markeredgecolor='gray',
                                      markeredgewidth=1.2,
                                      label='风圈')
        # 合并图例
        all_handles = color_patches + [mpl_patches.Circle((0, 0), 0, fc='none', ec='none')] + [wind_patch]
        all_labels = [p.get_label() for p in all_handles]

        loc = 'lower right' if scope == TyphoonScope.LARGE else 'upper right'
        ax.legend(handles=all_handles, labels=all_labels,
                  loc=loc, frameon=True, fancybox=True, shadow=False,
                  fontsize=7, title='图例', title_fontsize=8,
                  facecolor='white', edgecolor='gray')

    @staticmethod
    def _draw_title(ax: plt.Axes, storm_data: List[StormResponse]) -> None:
        if not storm_data:
            return
        latest = storm_data[0]
        year = latest.storm.year
        num = latest.storm.id[-2:]
        name = latest.storm.name
        dt = datetime.datetime.fromisoformat(latest.stormInfo.pubTime)

        line1 = f"{year}年第{num}号台风“{name}”路径图"
        line2 = dt.strftime("%Y年%m月%d日 %H:%M")

        ax.text(0.5, 1.01, f"{line1}\n{line2}",
                transform=ax.transAxes,
                fontsize=14, weight='bold',
                va='bottom', ha='center',
                linespacing=1.6)

    @staticmethod
    def _draw_footer(ax: plt.Axes) -> None:
        footer = (
            "注：风圈半径为经验估算，仅供参考。\n"
            "Data from QWeather | Map from Natural Earth\n"
            "Generated by KiBot"
        )
        ax.text(0.5, -0.05, footer,
                transform=ax.transAxes,
                fontsize=8, color='gray',
                va='top', ha='center',
                linespacing=1.5)

    @staticmethod
    def _estimate_wind_radii(latest: StormResponse) -> Dict[str, float]:
        """
        根据强度等级、中心气压、最大风速 估算 7/10/12 级风圈半径（km）
        """
        lvl = latest.stormInfo.type
        v = float(latest.stormInfo.windSpeed)  # m/s
        p = float(latest.stormInfo.pressure)  # hPa

        # 7级圈（R35）基础值
        v_kt = v * 1.944
        r35_km = max(80.0, min(300.0, (218 - 1.4 * v_kt) * 1.852))  # km

        # 10/12级倍数
        scale = {
            'TD': {'7': 1.0},
            'TS': {'7': 1.0, '10': 0.65},
            'STS': {'7': 1.0, '10': 0.75, '12': 0.45},
            'TY': {'7': 1.0, '10': 0.80, '12': 0.55},
            'STY': {'7': 1.0, '10': 0.85, '12': 0.60},
            'SuperTY': {'7': 1.0, '10': 0.90, '12': 0.65}
        }

        # 气压微调
        p_factor = 0.5 + (1010 - p) / 80  # 0.5~1.3倍

        radii: Dict[str, float] = {}
        for k, f in scale.get(lvl, {}).items():
            radii[k] = max(20.0, r35_km * f * p_factor)

        return radii

    @staticmethod
    def _format_time(pub_time: str) -> str:
        dt = datetime.datetime.fromisoformat(pub_time)
        return dt.strftime("%m-%d %H:%M")

    @staticmethod
    def _set_font():
        fonts = []
        system = platform.system()
        if system == 'Windows':
            candidates = ['Microsoft YaHei', 'SimHei', 'SimSun', 'KaiTi']
            fonts.append('DejaVu Sans')
        elif system == 'Darwin':  # macOS
            candidates = ['PingFang SC', 'Heiti SC', 'STHeiti', 'Songti SC']
            fonts.append('Helvetica')
        else:  # Linux
            candidates = ['Noto Sans CJK SC', 'WenQuanYi Micro Hei', 'SimHei']
            fonts.append('DejaVu Sans')

        for font_name in candidates:
            font_path = fm.findfont(fm.FontProperties(family=font_name))
            if font_path and font_name.lower() in fm.FontProperties(fname=font_path).get_name().lower():
                fonts.append(font_name)
                break
        else:
            print("绘制器未找到中文字体")

        plt.rcParams['font.family'] = fonts
        plt.rcParams['axes.unicode_minus'] = False

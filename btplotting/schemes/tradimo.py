from .blackly import Blackly


class Tradimo(Blackly):
    def _set_params(self):
        super()._set_params()

        dark_text = '#333333'

        self.barup = '#4CAF50'
        self.bardown = '#FF5252'

        self.barup_wick = self.barup
        self.bardown_wick = self.bardown

        self.barup_outline = self.barup
        self.bardown_outline = self.bardown

        self.text_color = '#222222'

        self.crosshair_line_color = '#444444'
        self.tag_pre_background_color = '#FFFFFF'
        self.tag_pre_text_color = dark_text

        self.legend_background_color = '#F5F5F5'
        self.legend_text_color = dark_text
        self.legend_click = 'hide'  # or 'mute'

        self.loc = '#265371'
        self.background_fill = '#FFFFFF'
        self.body_background_color = '#FFFFFF'
        self.border_fill = '#FFFFFF'
        self.axis_line_color = '#222222'
        self.grid_line_color = '#EEEEEE'
        self.tick_line_color = self.axis_line_color
        self.axis_text_color = dark_text
        self.plot_title_text_color = dark_text
        self.axis_label_text_color = dark_text

        self.table_color_even = '#404040'
        self.table_color_odd = '#333333'
        self.table_header_color = '#7A7A7A'

        self.tooltip_background_color = '#F5F5F5'
        self.tooltip_text_label_color = '#848EFF'
        self.tooltip_text_value_color = '#AAAAAA'

        self.tab_active_background_color = '#CCCCCC'
        self.tab_active_color = '#111111'

        self.table_color_even = '#FEFEFE'
        self.table_color_odd = '#EEEEEE'
        self.table_header_color = '#CCCCCC'

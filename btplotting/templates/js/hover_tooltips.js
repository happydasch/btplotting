// args: source, hover
// Hide NaN values from tooltips
var tmpl = Bokeh.require('core/util/templating');
if (hover.defaults == undefined || hover.defaults == false) {
    hover.defaults = hover.tooltips;
}
var index = -1;
if (cb_data.index.indices.length > 0) {
    index = cb_data.index.indices[0];
} else {
    // this is a workaround for a hit test bug:
    // https://github.com/bokeh/bokeh/issues/8787
    var column = source.get_column('index');
    for (var i = 0; i < column.length; i++) {
        if (column[i] == parseInt(cb_data.geometry.x)) {
            index = i;
            break;
        }
    }
}
if (index >= 0) {
    var ttips = [];
    for (var i = 0; i < hover.defaults.length; i++) {
        var val = tmpl.replace_placeholders(
            hover.defaults[i][1], source, index);
        if (val != 'NaN') {
            ttips.push(hover.defaults[i]);
        }
    }
    hover.tooltips = ttips;
} else {
    hover.tooltips = hover.defaults;
}

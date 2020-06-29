// args: source, hover
// Hide NaN values from tooltips
var tmpl = Bokeh.require("core/util/templating");
if (hover.defaults == undefined || hover.defaults == false) {
    hover.defaults = hover.tooltips;
}
if (cb_data.index.indices.length > 0) {
    var ttips = [];
    for (var i = 0; i < hover.defaults.length; i++) {
        var val = tmpl.replace_placeholders(
            hover.defaults[i][1],
            source,
            cb_data.index.indices[0]);
        if (val != "NaN") {
            ttips.push(hover.defaults[i]);
        }
    }
    hover.tooltips = ttips;
}
// args: axis, formatter, source
// We override this axis' formatter's `doFormat` method
// with one that maps index ticks to dates. Some of those dates
// are undefined (e.g. those whose ticks fall out of defined data
// range) and we must filter out and account for those, otherwise
// the formatter computes invalid visible span and returns some
// labels as 'ERR'.
// Note, after this assignment statement, on next plot redrawing,
// our override `doFormat` will be called directly
// -- FunctionTickFormatter.doFormat(), i.e. _this_ code, no longer
// executes.

axis.formatter.doFormat = function (ticks) {
    const dates = ticks.map(i => source.data.datetime[source.data.index.indexOf(i)]),
        valid = t => t !== undefined,
        labels = formatter.doFormat(dates.filter(valid));
    let i = 0;
    return dates.map(t => valid(t) ? labels[i++] : '');
};

// we do this manually only for the first time we are called
const labels = axis.formatter.doFormat(ticks);
return labels[index];

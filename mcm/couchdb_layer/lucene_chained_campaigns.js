function(doc) {
    log.debug('Chained campaign ' + doc._id);
    if (!doc.prepid) {
        return undefined;
    };
    var res = new Document();
    res.add(doc._id,                        { field: '_id',     store: 'yes', type: 'string' });
    res.add(doc.prepid,                     { field: 'prepid',  store: 'yes', type: 'string' });
    res.add(doc.enabled ? 'true' : 'false', { field: 'enabled', store: 'yes' });
    if (doc.campaigns) {
        for (var i = 0; i < doc.campaigns.length; i++) {
            res.add(doc.campaigns[i][0], { 'field': 'contains', store: 'yes' });
            if (doc.campaigns[i][1]) {
                res.add(doc.campaigns[i][1], { 'field': 'contains', store: 'yes' });
            }
        }
    };
    if (doc.history && doc.history.length > 0) {
        res.add(doc.history[0].updater.submission_date, { field: 'created', store: 'yes', type: 'string' });
    };
    return res;
}

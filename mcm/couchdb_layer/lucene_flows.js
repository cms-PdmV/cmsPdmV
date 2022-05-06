function(doc) {
    log.debug('Flow ' + doc._id);
    if (!doc.prepid) {
        return undefined;
    };
    var res = new Document();
    res.add(doc._id,           { field: '_id',           store: 'yes', type: 'string' });
    res.add(doc.prepid,        { field: 'prepid',        store: 'yes', type: 'string'});
    res.add(doc.next_campaign, { field: 'next_campaign', store: 'yes', type: 'string' });
    res.add(doc.approval,      { field: 'approval',      store: 'yes', type: 'string' });
    res.add(doc.next_campaign, { field: 'uses',          store: 'yes', type: 'string' });
    if (doc.allowed_campaigns) {
        for (var i = 0; i < doc.allowed_campaigns.length; i++) {
            res.add(doc.allowed_campaigns[i], { 'field': 'allowed_campaigns', store: 'yes' });
            res.add(doc.allowed_campaigns[i], { 'field': 'uses', store: 'yes' });
        }
    }
    if (doc.history && doc.history.length > 0) {
        res.add(doc.history[0].updater.submission_date, { field: 'created', store: 'yes', type: 'string' });
    };
    return res;
}

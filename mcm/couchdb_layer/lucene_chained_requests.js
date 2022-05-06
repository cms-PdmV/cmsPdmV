function(doc) {
    log.debug('Chained request ' + doc._id);
    if (!doc.prepid) {
        return undefined;
    };
    var res = new Document();
    res.add(doc._id,                { field: '_id', store: 'yes', type: 'string' });
    res.add(doc.prepid,             { field: 'prepid', store: 'yes', type: 'string' });
    res.add(doc.dataset_name,       { field: 'dataset_name', store: 'yes', type: 'string' });
    res.add(doc.status,             { field: 'status', store: 'yes' });
    res.add(doc.last_status,        { field: 'last_status', store: 'yes' });
    res.add(doc.member_of_campaign, { field: 'member_of_campaign', store: 'yes' });
    res.add(doc.validate ? 1 : 0,   { field: 'validate', store: 'yes', type: 'int' });
    res.add(doc.pwg,                { field: 'pwg', store: 'yes' });
    res.add(doc.step,               { field: 'step', store: 'yes', type: 'int' });
    if (doc.chain && doc.chain.length) {
        res.add(doc.chain[0], { field: 'root_request', store: 'yes' });
        for (var i = 0; i < doc.chain.length; i++) {
            res.add(doc.chain[i], { 'field': 'contains', store: 'yes' });
        }
    };
    if (doc.history && doc.history.length > 0) {
        res.add(doc.history[0].updater.submission_date, { field: 'created', store: 'yes', type: 'string' });
    };
    return res;
}

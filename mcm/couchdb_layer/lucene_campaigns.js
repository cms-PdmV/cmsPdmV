function(doc) {
    log.debug('Campaign ' + doc._id);
    if (!doc.prepid) {
        return undefined;
    };
    var res = new Document();
    res.add(doc._id, { field: '_id', store: 'yes', type: 'string' });
    res.add(doc.prepid, { field: 'prepid', store: 'yes', type: 'string' });
    res.add(doc.status, { field: 'status', store: 'yes', type: 'string' });
    res.add(doc.energy, { field: 'energy', store: 'yes', type: 'float' });
    res.add(doc.root, { field: 'root', store: 'yes', type: 'int' });
    res.add(doc.cmssw_release, { field: 'cmssw_release', store: 'yes', type: 'string' });
    if (doc.next) {
        for (var i = 0; i < doc.next.length; i++) {
            res.add(doc.next[i], { 'field': 'next', store: 'yes' });
        };
    };
    if (doc.history && doc.history.length > 0) {
        res.add(doc.history[0].updater.submission_date, { field: 'created', store: 'yes', type: 'string' });
    };
    return res;
} 

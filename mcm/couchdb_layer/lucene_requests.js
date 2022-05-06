function(doc) {
    log.debug('Request ' + doc._id);
    if (!doc.prepid) {
        return undefined;
    }
    var res = new Document();
    res.add(doc._id, { field: '_id', store: 'yes', type: 'string' });
    res.add(doc.approval, { field: 'approval', store: 'yes' });
    res.add(doc.extension, { field: 'extension', store: 'yes', type: 'int' });
    res.add(doc.mcdb_id, { field: 'mcdb_id', store: 'yes', type: 'int' });
    res.add(doc.cmssw_release, { field: 'cmssw_release', store: 'yes' });
    res.add(doc.prepid, { field: 'prepid', store: 'yes' });
    res.add(doc.status, { field: 'status', store: 'yes' });
    res.add(doc.pwg, { field: 'pwg', store: 'yes' });
    res.add(doc.dataset_name, { field: 'dataset_name', store: 'yes' });
    res.add(doc.member_of_campaign, { field: 'member_of_campaign', store: 'yes' });
    res.add(doc.flown_with, { field: 'flown_with', store: 'yes' });
    res.add(doc.process_string, { field: 'process_string', store: 'yes' });
    res.add(doc.energy, { field: 'energy', store: 'yes', type: 'float' });
    res.add(doc.priority, { field: 'priority', store: 'yes', type: 'int' });
    if (doc.tags) {
        for (var i in doc.tags) {
            res.add(doc.tags[i], { field: 'tags', store: 'yes' });
        }
    }
    if (doc.member_of_chain) {
        for (var i in doc.member_of_chain) {
            res.add(doc.member_of_chain[i], { field: 'member_of_chain', store: 'yes' });
        }
    }
    if (doc.history) {
        var actors = [];
        for (var i in doc.history) {
            var actor = doc.history[i].updater.author_username;
            if (actors.indexOf(actor) == -1) {
                res.add(actor, { field: 'actor', store: 'yes' });
                actors.push(actor);
            }
        }
    }
    if (doc.output_dataset) {
        for (i in doc.output_dataset) {
            res.add(doc.output_dataset[i], { field: 'output_dataset', store: 'yes' });
        }
    }
    if (doc.reqmgr_name) {
        for (var i in doc.reqmgr_name) {
            res.add(doc.reqmgr_name[i].name, { field: 'reqmgr_name', store: 'yes' });
        }
    }
    if (doc.input_dataset) {
        res.add(doc.input_dataset, { field: 'input_dataset', store: 'yes' })
    };
    if (doc.pileup_dataset_name) {
        res.add(doc.pileup_dataset_name, { field: 'pileup_dataset_name', store: 'yes' });
    };
    if (doc.interested_pwg) {
        for (var i in doc.interested_pwg) {
            res.add(doc.interested_pwg[i], { field: 'interested_pwg', store: 'yes' });
        }
    }
    if (doc.history && doc.history.length > 0) {
        res.add(doc.history[0].updater.submission_date, { field: 'created', store: 'yes', type: 'string' });
    };
    return res;
}

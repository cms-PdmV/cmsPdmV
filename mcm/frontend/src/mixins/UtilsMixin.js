export const utilsMixin = {

  methods: {

    checkAttributes(columns, items) {
      columns = columns.map(x => x.dbName);
      for (const item of items) {
        const ignore = ['_id', '_rev', '_actions'];
        let surplus = Object.keys(item).filter(x => !columns.includes(x)).filter(x => !ignore.includes(x)).join(', ');
        let missing = columns.filter(x => !Object.keys(item).includes(x)).filter(x => !ignore.includes(x)).join(', ');
        if (surplus.length) {
          console.warn(`${item.prepid} no columns: ${surplus}`);
        }
        if (missing.length) {
          console.warn(`${item.prepid} no attributes: ${missing}`);
        }
      }

    },
    dasLink(dataset) {
      return 'https://cmsweb.cern.ch/das/request?input=' + dataset;
    },
    sequenceName(sequence) {
      if (!sequence || !sequence.datatier) {
        return '<no datatier>';
      }
      if (Array.isArray(sequence.datatier)) {
        return sequence.datatier.join(',');
      }
      return sequence.datatier;
    },
    makeDriver(sequence) {
      let driver = 'cmsDriver.py ';
      for (const key of Object.keys(sequence).sort()) {
        if (key == 'index') {
          continue;
        }
        const value = sequence[key];
        if (!value || value.length === 0) {
          continue;
        }
        driver += `--${key} ${sequence[key]} `;
      }
      return driver.trim();
    }
  },
};

import axios from 'axios';

export const editPageMixin = {
  data() {
    return {
      prepid: undefined,
      loading: false,
      object: {},
      editable: {},
    };
  },
  created() {
    let query = Object.assign({}, this.$route.query);
    this.prepid = query.prepid;
    this.fetchEditable();
  },
  methods: {
    fetchEditable: function() {
      let url = 'restapi/' + this.databaseName + '/get_editable';
      if (this.prepid) {
        url += '/' + this.prepid;
      }
      this.loading = true;
      axios
        .get(url)
        .then(
          (response) => {
            if (response.data.results) {
              this.object = response.data.results.object;
              this.editable = response.data.results.editing_info;
              delete this.object.history;
              this.loading = false;
            } else if (response.data.message) {
              this.showError(response.data.message);
              this.loading = false;
            }
          },
          (error) => {
            this.showError(error);
            this.loading = false;
          },
        )
        .catch((error) => {
          this.showError(error);
          this.loading = false;
        });
    },
    save: function(showItem) {
      let url = 'restapi/' + this.databaseName + '/update';
      this.loading = true;        
      axios
        .post(url, this.object)
        .then(
          (response) => {
            if (response.data.results) {
              if (showItem) {
                window.location = this.databaseName + '?prepid=' + response.data.prepid;
              } else {
                this.fetchEditable();
              }
            } else if (response.data.message) {
              this.showError(response.data.message);
              this.loading = false;
            }
          },
          (error) => {
            this.showError(error);
            this.loading = false;
          },
        )
        .catch((error) => {
          this.showError(error);
          this.loading = false;
        });
    },
    promptDelete: function(item) {
      this.$refs['delete-prompt'].open(this.databaseName, item, (response) => {
        if (response.results) {
          window.location = this.databaseName;
        } else if (response.message) {
          this.showError(response.message);
        }
      }, (error) => {
        this.showError(error);
      });
    },
    cancelEdit: function() {
      window.location = this.databaseName + '?prepid=' + this.prepid;
    },
    showError: function(errorMessage) {
      this.$refs['error-dialog'].open(errorMessage);
    },
  },
};

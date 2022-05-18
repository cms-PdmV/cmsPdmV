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
              let editableObject = response.data.results.object;
              if (this.prepareForEdit) {
                this.prepareForEdit(editableObject);
              }
              this.object = editableObject;
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
      this.loading = true;
      let editableObject = JSON.parse(JSON.stringify(this.object));
      if (this.prepareForSave) {
        this.prepareForSave(editableObject);
      }
      let url = 'restapi/' + this.databaseName;
      let request;
      if (this.prepid) {
        request = axios.post(url + '/update', editableObject)
      } else {
        request = axios.put(url + '/save', editableObject)
      }
      request.then(
          (response) => {
            if (response.data.results) {
              if (showItem) {
                window.location = this.databaseName + '?prepid=' + response.data.prepid;
              } else {
                this.prepid = response.data.prepid;
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
      if (this.prepid) {
        window.location = this.databaseName + '?prepid=' + this.prepid;
      } else {
        window.location = this.databaseName;
      }
    },
    showError: function(errorMessage) {
      this.$refs['error-dialog'].open(errorMessage);
    },
  },
};

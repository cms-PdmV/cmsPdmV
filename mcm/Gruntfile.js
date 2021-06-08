module.exports = function(grunt) {
    grunt.initConfig({
        concat: {
            js1: {
                src: [
                    'scripts/jquery-1.12.4.min.js',
                    'scripts/jquery.cookie.js',
                    'scripts/angular.min.js',
                    'scripts/underscore.min.js',
                    'scripts/ui-bootstrap-tpls-0.8.0.min.js'
                ],
                dest: 'scripts/build/mcm.deps1.js'
            },
            js2: {
                src: [
                    'scripts/bindonce.js',
                    'scripts/bootstrap-tokenfield.min.js',
                    'scripts/typeahead.min.js',
                ],
                dest: 'scripts/build/mcm.deps2.js'
            },
            mcmcss: {
                src: [
                    'scripts/css/bootstrap.min.css',
                    'scripts/css/tokenfield-typeahead.css',
                    'scripts/css/bootstrap-tokenfield.css',
                    'scripts/css/mcm.css'
                ],
                dest:'scripts/build/mcmcss.css'
            }
        }
    });
    grunt.loadNpmTasks('grunt-contrib-concat');
    grunt.registerTask('default', ['concat'])
};
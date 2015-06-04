;(function (define) {
    'use strict';

    define(['backbone',
            'underscore',
            'gettext',
            'js/components/header/views/header',
            'js/components/header/models/header',
            'js/components/tabbed/views/tabbed_view'],
           function (Backbone, _, gettext, HeaderView, HeaderModel, TabbedView) {
               var TeamTabView = Backbone.View.extend({
                   initialize: function() {
                       this.headerModel = new HeaderModel({
                           description: gettext("Course teams are organized into topics created by course instructors. Try to join others in an existing team before you decide to create a new team!"),
                           title: gettext("Teams")
                       });
                       this.headerView = new HeaderView({
                           model: this.headerModel
                       });
                       // TODO replace this with actual views!
                       var TempTabView = Backbone.View.extend({
                           initialize: function (options) {
                               this.text = options.text;
                           },

                           render: function () {
                               this.$el.text(this.text)
                           }
                       });
                       this.tabbedView = new TabbedView({
                           tabs: [{
                               title: gettext('My Teams'),
                               url: 'teams',
                               view: new TempTabView({text: gettext('This is the new Teams tab.')})
                           }, {
                               title: gettext('Browse'),
                               url: 'browse',
                               view: new TempTabView({text: gettext('Browse team topics here.')})
                           }]
                       });
                       Backbone.history.start();
                   },

                   render: function() {
                       this.$el.prepend(this.headerView.$el);
                       this.headerView.render();
                       this.$el.append(this.tabbedView.$el);
                       this.tabbedView.render();
                   }
               });

               return TeamTabView;
           });
}).call(this, define || RequireJS.define);

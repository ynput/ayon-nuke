# import pyblish.api


# class IntegrateProres(pyblish.api.InstancePlugin):

#     label = "Integrate untracked prores"
#     order = pyblish.api.IntegratorOrder + 0.52
#     hosts = ['nuke']
#     families = ["render",'plate','prerender']
#     # default_template_name = "publish"

#     def process(self, instance):
#         self.log.info("Integrating untracked prores")
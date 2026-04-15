def pytest_configure(config):
    pluginmanager = config.pluginmanager
    for name in ("cacheprovider", "pytest_cacheprovider", "stepwise", "pytest_stepwise"):
        plugin = pluginmanager.get_plugin(name)
        if plugin is not None:
            pluginmanager.unregister(plugin)

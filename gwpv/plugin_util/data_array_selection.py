# From:
# https://github.com/Kitware/ParaView/blob/master/Examples/Plugins/PythonAlgorithm/PythonAlgorithmExamples.py
def create_modified_callback(anobject):
    import weakref
    weakref_obj = weakref.ref(anobject)
    anobject = None
    def _markmodified(*args, **kwars):
        o = weakref_obj()
        if o is not None:
            o.Modified()
    return _markmodified

import logging


def get_timestep(algorithm, logger=None):
    if logger is None:
        logger = logging.getLogger(__name__)
    logger.debug("Getting current timestep...")
    executive = algorithm.GetExecutive()
    outInfo = executive.GetOutputInformation(0)
    if not outInfo.Has(executive.UPDATE_TIME_STEP()):
        logger.debug("No `UPDATE_TIME_STEP` found. Return 0.")
        return 0.
    timestep = outInfo.Get(executive.UPDATE_TIME_STEP())
    logger.debug("Found `UPDATE_TIME_STEP`: {}".format(timestep))
    return timestep


def set_timesteps(algorithm, timesteps, logger=None):
    if logger is None:
        logger = logging.getLogger(__name__)
    executive = algorithm.GetExecutive()
    outInfo = executive.GetOutputInformation(0)
    outInfo.Remove(executive.TIME_STEPS())
    for timestep in timesteps:
        outInfo.Append(executive.TIME_STEPS(), timestep)
    outInfo.Remove(executive.TIME_RANGE())
    outInfo.Append(executive.TIME_RANGE(), timesteps[0])
    outInfo.Append(executive.TIME_RANGE(), timesteps[-1])
    logger.debug("Set data timesteps to {}.".format(
        outInfo.Get(executive.TIME_RANGE())))

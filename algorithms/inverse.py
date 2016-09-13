from ctapipe.core import Component
from time import sleep



class Inverse(Component):
    """Add class represents a Stage for pipeline.

    """
    def init(self):
        self.log.debug("--- Add init ---")
        return True

    def run(self, inputs):
        sleep(.1)
        if  inputs:
            self.log.debug("Inverse receive {}".format(inputs))
            return int(inputs) * -1

    def finish(self):
        self.log.debug("--- Add finish ---")
        pass

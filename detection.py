class BirdDetection:
    __slots__ = ('timestamp_utc', 'chunk_interval_sec', 'species', 'confidence')

    def __init__(self, timestamp_utc, chunk_interval_sec, species, confidence):
        self.timestamp_utc = timestamp_utc
        self.chunk_interval_sec = chunk_interval_sec
        self.species = species
        self.confidence = confidence

    def __repr__(self):
        return (f"BirdDetection(species='{self.species}', "
                f"confidence={self.confidence:.2f}, "
                f"interval={self.chunk_interval_sec}, "
                f"time='{self.timestamp_utc}')")
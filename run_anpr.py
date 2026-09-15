from database.anpr_system import ANPRSystem

system = ANPRSystem()

# Register camera
system.register_camera(
    "CAM-01",
    "Main Road",
    "Road 1"
)

# Give the video path here
system.process_camera(
    "CAM-01",
    r"/Users/ayushkumar/Desktop/SIH/vectra/data/videos/cam3.mp4"
)

system.stop()
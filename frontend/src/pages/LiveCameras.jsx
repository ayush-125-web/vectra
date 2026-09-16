const cameras = [
  {
    id: 'CAM-01',
    name: 'Main Road',
    road: 'Road 1',
    video: '/cameras/CAM-01.mp4',
  },
  {
    id: 'CAM-02',
    name: 'Kilpauk',
    road: 'Road 2',
    video: '/cameras/CAM-02.mp4',
  },
  {
    id: 'CAM-03',
    name: 'Civic Center',
    road: 'Road 3',
    video: '/cameras/CAM-03.mp4',
  },
  {
    id: 'CAM-04',
    name: 'Guindy',
    road: 'Road 4',
    video: '/cameras/CAM-04.mp4',
  },
  {
    id: 'CAM-05',
    name: 'T Nagar',
    road: 'Road 5',
    video: '/cameras/CAM-05.mp4',
  },
]

export default function LiveCameras() {
  return (
    <div className="p-8 space-y-6">

      {/* HEADER */}
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold text-ink-100">
            Live Cameras
          </h1>

          <p className="text-sm text-ink-500 mt-1">
            Monitor all camera feeds
          </p>
        </div>

        <span className="text-xs font-mono text-signal-red border border-signal-red/40 bg-signal-red/10 px-2.5 py-1 rounded">
          ● LIVE
        </span>
      </header>


      {/* CAMERA GRID */}
      <div className="grid grid-cols-2 gap-4">

        {cameras.map(camera => (
          <div
            key={camera.id}
            className="border border-base-500 bg-base-800 rounded overflow-hidden"
          >

            {/* CAMERA HEADER */}
            <div className="px-4 py-3 flex items-center justify-between border-b border-base-500">

              <div>
                <div className="font-mono text-sm text-ink-100">
                  {camera.id}
                </div>

                <div className="text-xs text-ink-500 mt-1">
                  {camera.name} · {camera.road}
                </div>
              </div>

              <span className="text-[10px] font-mono text-signal-red">
                ● LIVE
              </span>

            </div>


            {/* VIDEO */}
            <video
              className="w-full aspect-video object-cover bg-black"
              src={camera.video}
              autoPlay
              muted
              loop
              playsInline
              controls
            />

          </div>
        ))}

      </div>

    </div>
  )
}
async function request(url) {
  const response = await fetch(url)
  const data = await response.json()

  if (!response.ok) {
    throw new Error(
      data.error ||
      (data.plate_number
        ? `Vehicle ${data.plate_number} not found`
        : 'Request failed')
    )
  }

  return data
}



export async function getVehicle(plate) {
  return request(`/api/vehicle/${encodeURIComponent(plate)}`)
}

export async function getBlacklist() {
  return request('/api/blacklist')
}

export async function getTrajectory(plate) {
  const data = await request(
    `/api/trajectory/${encodeURIComponent(plate)}`
  )

  return data.trajectory
}


export async function getLastLocation(plate) {
  return request(
    `/api/last-location/${encodeURIComponent(plate)}`
  )
}
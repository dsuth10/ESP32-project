[Windows.Devices.Bluetooth.BluetoothLEDevice,Windows.Devices.Bluetooth,ContentType=WindowsRuntime] | Out-Null
$selector = [Windows.Devices.Bluetooth.BluetoothLEDevice]::GetDeviceSelector()
$devices = [Windows.Devices.Enumeration.DeviceInformation]::FindAllAsync($selector).GetAwaiter().GetResult()
foreach ($d in $devices) {
    if ($d.Name -match "ESP32") {
        $ble = [Windows.Devices.Bluetooth.BluetoothLEDevice]::FromIdAsync($d.Id).GetAwaiter().GetResult()
        Write-Output "Device: $($d.Name) | ConnectionStatus: $($ble.ConnectionStatus)"
    }
}

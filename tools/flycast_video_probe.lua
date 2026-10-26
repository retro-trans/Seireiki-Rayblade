-- Read-only guest video telemetry for an isolated Flycast cold boot.
-- Copy beside the isolated emulator as flycast.lua; writes video-probe.csv there.
-- Does not press buttons, load save states or write guest memory.
local frame = 0
local out = assert(io.open('video-probe.csv', 'w'))
out:write('frame,cable,region,broadcast,width,height,spg_control,spg_load,fb_r_ctrl,vga_code_word\n')
flycast_callbacks = {
    vblank = function()
        frame = frame + 1
        if frame % 60 == 0 then
            out:write(string.format('%d,%d,%d,%d,%d,%d,%08x,%08x,%08x,%08x\n',
                frame, flycast.config.general.Cable, flycast.config.general.Region,
                flycast.config.general.Broadcast, flycast.state.display.width,
                flycast.state.display.height, flycast.memory.read32(0xa05f80d0),
                flycast.memory.read32(0xa05f80d8), flycast.memory.read32(0xa05f8044),
                flycast.memory.read32(0x8c0a6d24)))
            out:flush()
        end
        if frame == 1200 then
            out:close()
            flycast.emulator.exit()
        end
    end
}

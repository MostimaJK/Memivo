"""Native desktop placement, performed before the window becomes visible."""


def center_windows_window(window):
    # Work entirely in WinForms' native coordinate space so mixed screen origins
    # and DPI don't get multiplied a second time by pywebview.move/resize.
    import ctypes
    from System.Drawing import Point, Size
    from System.Windows.Forms import Cursor, FormStartPosition, Screen

    form = window.native
    area = Screen.FromPoint(Cursor.Position).WorkingArea
    form.StartPosition = FormStartPosition.Manual
    # Move the still-hidden handle to its target screen before reading its DPI.
    form.Location = Point(area.X, area.Y)
    # DeviceDpi can remain 96 with the .NET Framework host; use the HWND DPI,
    # matching the coordinate conversion used by pywebview's WinForms backend.
    dpi = ctypes.windll.user32.GetDpiForWindow(ctypes.c_void_p(form.Handle.ToInt64()))
    scale = (dpi or 96) / 96
    margin = round(24 * scale)
    width = min(round(1480 * scale), max(1, area.Width - 2 * margin))
    height = min(round(960 * scale), max(1, area.Height - 2 * margin))
    form.MinimumSize = Size(min(round(1040 * scale), width), min(round(700 * scale), height))
    form.Size = Size(width, height)
    form.Location = Point(area.X + (area.Width - form.Width) // 2,
                          area.Y + (area.Height - form.Height) // 2)

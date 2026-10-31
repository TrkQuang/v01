{pkgs}: {
  deps = [
    pkgs.chromedriver
    pkgs.chromium
    pkgs.xorg.xorgserver
  ];
}

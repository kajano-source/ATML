Name:           atml
Version:        1.4.0
Release:        1%{?dist}
Summary:        ATML template compiler CLI, HTML converter runtime, and editor support
License:        MIT
URL:            https://example.com/atml
BuildArch:      noarch
Requires:       python3
Recommends:     python3-tkinter

%description
ATML 1.4.0: compiler CLI (`atml`), HTML converter runtime, example
projects, VS Code syntax support, and .atml file association.

%install
rm -rf %{buildroot}
install -dm755 %{buildroot}%{_bindir} %{buildroot}%{_datadir}/atml \
  %{buildroot}%{_datadir}/applications %{buildroot}%{_datadir}/mime/packages
cp -r %{_sourcedir}/compiler %{buildroot}%{_datadir}/atml/ 2>/dev/null || :
cp -r %{_sourcedir}/runtime %{buildroot}%{_datadir}/atml/ 2>/dev/null || :
cp -r %{_sourcedir}/examples %{buildroot}%{_datadir}/atml/ 2>/dev/null || :
cp -r %{_sourcedir}/vscode-atml %{buildroot}%{_datadir}/atml/ 2>/dev/null || :
cat > %{buildroot}%{_bindir}/atml <<'EOF'
#!/usr/bin/env bash
if [ -f %{_datadir}/atml/compiler/atmlc.py ]; then
  exec python3 %{_datadir}/atml/compiler/atmlc.py "$@"
else
  echo "ATML 1.4.0 (%{_datadir}/atml)" >&2
  ls %{_datadir}/atml >&2
fi
EOF
chmod 755 %{buildroot}%{_bindir}/atml
install -Dm644 %{_sourcedir}/installer/arch/atml.desktop %{buildroot}%{_datadir}/applications/atml.desktop

%files
%{_bindir}/atml
%{_datadir}/atml/
%{_datadir}/applications/atml.desktop

%changelog
* Sun Oct 05 2026 ATML contributors - 1.4.0-1
- 1.4.0: `atml --version`, `check` accepts dirs/multiple files; extension sugar/shapes synced.
* Sat Oct 04 2026 ATML contributors - 1.3.2-1
- 1.3.2: drop WAAPI fast-path (phantom actor offsets); text actors keep font-size/weight/family.
- 1.3.1: extension finds user-install compiler without PATH; visible run notifications.
- 1.3.0: ATML debug provider (F5 runs in browser).
- 1.2.0: new `atml run` (open in browser) + VS Code `atml.run` command.
- 1.1.2: installer shims exec compiler/atmlc.py; vsix packaging fixes.
- 1.1.1: `build -o` creates missing output directories.
- 1.1.0: new `atml publish` site publisher (multi-page, assets, sitemap).

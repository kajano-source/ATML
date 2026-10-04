# Install ATML 1.4.1

## Option 1 — from git (any Linux / macOS with python3)

```sh
git clone https://github.com/kajano-source/ATML.git
cd ATML
bash scripts/install.sh --yes
export PATH="$HOME/.local/bin:$PATH"
atml --version
```

## Option 2 — from the AUR (Arch Linux)

```sh
yay -S atml
```

or with `paru`:

```sh
paru -S atml
```

Then verify:

```sh
atml --version
```

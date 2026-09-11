#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python -m pip install -r requirements.txt
# Keep Node and Cobalt inside the deploy artifact; never depend on a public instance.
mkdir -p .runtime
NODE_VERSION=22.23.2
NODE_ARCH="$(uname -m)"
case "$NODE_ARCH" in x86_64) NODE_ARCH=x64;; aarch64) NODE_ARCH=arm64;; *) exit 1;; esac
NODE_DIST="node-v${NODE_VERSION}-linux-${NODE_ARCH}"
curl --fail --location --retry 3 "https://nodejs.org/dist/v${NODE_VERSION}/${NODE_DIST}.tar.xz" -o .runtime/node.tar.xz
curl --fail --location --retry 3 "https://nodejs.org/dist/v${NODE_VERSION}/SHASUMS256.txt" -o .runtime/SHASUMS256.txt
(cd .runtime; cp node.tar.xz "${NODE_DIST}.tar.xz"; grep " ${NODE_DIST}.tar.xz$" SHASUMS256.txt | sha256sum --check; tar -xf node.tar.xz; rm node.tar.xz "${NODE_DIST}.tar.xz")
ln -sfn "$NODE_DIST" .runtime/node
export PATH="$PWD/.runtime/node/bin:$PATH"
npm install --prefix .runtime/pnpm pnpm@9.6.0 --no-audit --no-fund
COBALT_COMMIT=a636575b09de1fc55d9b8cd98cac88f5f2f16b42
# A prior build can be canceled mid-clone, leaving a partial, non-git directory
# in the persisted build cache; a plain `git clone` into it then fails with
# "already exists and is not an empty directory". Self-heal by removing it.
# (Do not use `git rev-parse --is-inside-work-tree` here: run from inside
# .runtime/cobalt without its own .git, git walks up to this repo's own
# .git and reports true, masking a partial/missing checkout.)
if [ -d .runtime/cobalt ] && [ ! -d .runtime/cobalt/.git ]; then
    rm -rf .runtime/cobalt
fi
if [ ! -d .runtime/cobalt/.git ]; then git clone --filter=blob:none https://github.com/imputnet/cobalt.git .runtime/cobalt; fi
git -C .runtime/cobalt fetch origin "$COBALT_COMMIT"
git -C .runtime/cobalt checkout --detach "$COBALT_COMMIT"
(cd .runtime/cobalt; ../node/bin/node ../pnpm/node_modules/pnpm/bin/pnpm.cjs install --filter '@imput/cobalt-api...' --frozen-lockfile --prod)

# YouTube's server-side bot check (HTTP 403 "Sign in to confirm you're not a
# bot") blocks yt-dlp from datacenter IPs like Render's without a PO token.
# bgutil-ytdlp-pot-provider mints tokens locally (no cookies, no browser, no
# account) via a small Node server that the pip plugin (in requirements.txt)
# queries over loopback at request time.
POTPROVIDER_COMMIT=37169ee2656e08c5c2e5dc9df4c598c0cb4c88a8
if [ -d .runtime/potprovider ] && [ ! -d .runtime/potprovider/.git ]; then
    rm -rf .runtime/potprovider
fi
if [ ! -d .runtime/potprovider/.git ]; then git clone --filter=blob:none https://github.com/Brainicism/bgutil-ytdlp-pot-provider.git .runtime/potprovider; fi
git -C .runtime/potprovider fetch origin "$POTPROVIDER_COMMIT"
git -C .runtime/potprovider checkout --detach "$POTPROVIDER_COMMIT"
(cd .runtime/potprovider/server; npm ci; npx tsc; npm prune --omit=dev)

command -v ffmpeg
command -v ffprobe
node --version

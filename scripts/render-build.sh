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
command -v ffmpeg
command -v ffprobe
node --version

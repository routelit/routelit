git submodule update --init --recursive
cd src/client
pnpm install
pnpm build:lib
pnpm build

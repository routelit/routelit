CLIENT_GIT_TAG=0.4.1

cd src/client
git fetch --tags
git checkout $CLIENT_GIT_TAG
pnpm install
pnpm build:lib
pnpm build

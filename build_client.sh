
if [ ! -d "src/client" ]; then
    cd src
    git clone https://github.com/routelit/routelit-client.git client
    cd ..
fi

cd src/client
pnpm build:lib
pnpm build
cd ../..

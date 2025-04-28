import { RouteLitManager } from "./manager";

function initManager(dataElementSelector: string) {
  const routelitData = document.getElementById(
    dataElementSelector
  ) as HTMLInputElement;
  if (!routelitData) {
    throw new Error(`'${dataElementSelector}' element not found.`);
  }
  const componentsTree = JSON.parse(routelitData.value);
  const manager = new RouteLitManager({ componentsTree });
  return manager;
}

export default initManager;

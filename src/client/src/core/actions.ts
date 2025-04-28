export function applyAddAction(
  componentsTree: RouteLitComponent[],
  action: AddAction
) {
  let target = componentsTree;
  for (let i = 0; i < action.address.length - 1; i++) {
    if (!target[action.address[i]].children) {
      target[action.address[i]].children = [];
    }
    target = target[action.address[i]].children!;
  }
  target.splice(action.address[action.address.length - 1], 0, action.element);
}

export function applyRemoveAction(
  componentsTree: RouteLitComponent[],
  action: RemoveAction
) {
  let target = componentsTree;
  for (let i = 0; i < action.address.length - 1; i++) {
    if (!target[action.address[i]].children) {
      target[action.address[i]].children = [];
    }
    target = target[action.address[i]].children!;
  }
  target.splice(action.address[action.address.length - 1], 1);
}

export function applyUpdateAction(
  componentsTree: RouteLitComponent[],
  action: UpdateAction
) {
  let target = componentsTree;
  for (let i = 0; i < action.address.length - 1; i++) {
    if (!target[action.address[i]].children) {
      target[action.address[i]].children = [];
    }
    target = target[action.address[i]].children!;
  }
  target[action.address[action.address.length - 1]].props = action.props;
}

export function prependAddressToActions(
  actionResponse: ActionsResponse,
  address: number[]
): ActionsResponse {
  return {
    ...actionResponse,
    actions: actionResponse.actions.map((action) => {
      return { ...action, address: address.concat(action.address) };
    }),
  };
}

export function applyActions(
  componentsTree: RouteLitComponent[],
  actions: Action[]
) {
  actions.forEach((action) => {
    switch (action.type) {
      case "add":
        applyAddAction(componentsTree, action as AddAction);
        break;
      case "remove":
        applyRemoveAction(componentsTree, action as RemoveAction);
        break;
      case "update":
        applyUpdateAction(componentsTree, action as UpdateAction);
        break;
    }
  });
}

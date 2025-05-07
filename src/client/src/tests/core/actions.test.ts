/// <reference path="../../types.d.ts" />
import {
  applyAddAction,
  applyRemoveAction,
  applyUpdateAction,
  applyActions,
  prependAddressToActions
} from '../../core/actions';

describe('Actions', () => {
  describe('applyAddAction', () => {
    it('should add a component at the specified address', () => {
      const componentsTree: RouteLitComponent[] = [
        {
          name: 'parent',
          key: 'parent',
          props: {},
          address: [0],
          children: [
            {
              name: 'child1',
              key: 'child1',
              props: {},
              address: [0, 0]
            }
          ]
        }
      ];

      const newComponent: RouteLitComponent = {
        name: 'newChild',
        key: 'newChild',
        props: { id: 'new' },
        address: [0, 1]
      };

      const addAction: AddAction = {
        type: 'add',
        address: [0, 1],
        element: newComponent
      };

      applyAddAction(componentsTree, addAction);

      // Check that the new component was added at the right position
      expect(componentsTree[0].children?.length).toBe(2);
      expect(componentsTree[0].children?.[1]).toEqual(newComponent);
    });

    it('should handle nested addresses correctly', () => {
      const componentsTree: RouteLitComponent[] = [
        {
          name: 'parent',
          key: 'parent',
          props: {},
          address: [0],
          children: [
            {
              name: 'child',
              key: 'child',
              props: {},
              address: [0, 0],
              children: []
            }
          ]
        }
      ];

      const newComponent: RouteLitComponent = {
        name: 'deepChild',
        key: 'deepChild',
        props: {},
        address: [0, 0, 0]
      };

      const addAction: AddAction = {
        type: 'add',
        address: [0, 0, 0],
        element: newComponent
      };

      applyAddAction(componentsTree, addAction);

      // Check that the new component was added at the right position
      expect(componentsTree[0].children?.[0].children?.length).toBe(1);
      expect(componentsTree[0].children?.[0].children?.[0]).toEqual(newComponent);
    });
  });

  describe('applyRemoveAction', () => {
    it('should remove a component at the specified address', () => {
      const componentsTree: RouteLitComponent[] = [
        {
          name: 'parent',
          key: 'parent',
          props: {},
          address: [0],
          children: [
            {
              name: 'child1',
              key: 'child1',
              props: {},
              address: [0, 0]
            },
            {
              name: 'child2',
              key: 'child2',
              props: {},
              address: [0, 1]
            }
          ]
        }
      ];

      const removeAction: RemoveAction = {
        type: 'remove',
        address: [0, 0]
      };

      applyRemoveAction(componentsTree, removeAction);

      // Check that the component was removed
      expect(componentsTree[0].children?.length).toBe(1);
      expect(componentsTree[0].children?.[0].key).toBe('child2');
    });
  });

  describe('applyUpdateAction', () => {
    it('should update props of a component at the specified address', () => {
      const componentsTree: RouteLitComponent[] = [
        {
          name: 'parent',
          key: 'parent',
          props: { id: 'parent' },
          address: [0]
        }
      ];

      const updateAction: UpdateAction = {
        type: 'update',
        address: [0],
        props: { id: 'updated', newProp: 'value' }
      };

      applyUpdateAction(componentsTree, updateAction);

      // Check that the props were updated
      expect(componentsTree[0].props).toEqual({ id: 'updated', newProp: 'value' });
    });
  });

  describe('applyActions', () => {
    it('should apply multiple actions in sequence', () => {
      const componentsTree: RouteLitComponent[] = [
        {
          name: 'parent',
          key: 'parent',
          props: { id: 'parent' },
          address: [0],
          children: []
        }
      ];

      const addAction: AddAction = {
        type: 'add',
        address: [0, 0],
        element: {
          name: 'child',
          key: 'child',
          props: { id: 'child' },
          address: [0, 0]
        }
      };

      const updateAction: UpdateAction = {
        type: 'update',
        address: [0],
        props: { id: 'updated-parent' }
      };

      const actions: (AddAction | UpdateAction)[] = [addAction, updateAction];

      applyActions(componentsTree, actions);

      // Check that both actions were applied
      expect(componentsTree[0].props).toEqual({ id: 'updated-parent' });
      expect(componentsTree[0].children?.length).toBe(1);
      expect(componentsTree[0].children?.[0].key).toBe('child');
    });
  });

  describe('prependAddressToActions', () => {
    it('should prepend the given address to all action addresses', () => {
      const addAction: AddAction = {
        type: 'add',
        address: [0],
        element: { name: 'div', key: 'test', props: {}, address: [0] }
      };

      const updateAction: UpdateAction = {
        type: 'update',
        address: [1],
        props: { id: 'updated' }
      };

      const actionsResponse: ActionsResponse = {
        actions: [addAction, updateAction],
        target: 'fragment'
      };

      const address = [2, 3];

      const result = prependAddressToActions(actionsResponse, address);

      // Check that addresses were properly prepended
      expect(result.actions[0].address).toEqual([2, 3, 0]);
      expect(result.actions[1].address).toEqual([2, 3, 1]);

      // Check that the original response was not modified
      expect(actionsResponse.actions[0].address).toEqual([0]);
      expect(actionsResponse.actions[1].address).toEqual([1]);
    });
  });
});

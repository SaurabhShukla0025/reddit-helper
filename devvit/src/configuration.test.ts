import { test } from 'node:test';
import assert from 'node:assert/strict';
import { installationPolicy } from './configuration.ts';

test('installation policy reads native selection and permission records', () => {
  const policy = installationPolicy({
    'operation-mode': { fieldType: 5, selectionValue: { values: ['playtest'] } },
    'approved-community': { fieldType: 0, stringValue: 'saurabhhelpertest' },
    'permission-reference': { fieldType: 0, stringValue: 'owner playtest' },
  });
  assert.equal(policy.mode, 'playtest');
  assert.equal(policy.community, 'saurabhhelpertest');
  assert.equal(policy.permissionReference, 'owner playtest');
  assert.equal(policy.communityPermission, '');
});

test('missing installation settings never enable the workflow with defaults', () => {
  const policy = installationPolicy();
  assert.equal(policy.mode, '');
  assert.equal(policy.community, '');
  assert.equal(policy.permissionReference, '');
});

test('malformed or wrongly typed mode cannot enable the workflow', () => {
  for (const field of [
    { fieldType: 0, selectionValue: { values: ['approved'] } },
    { fieldType: 5, selectionValue: { values: ['playtest', 'approved'] } },
    { stringValue: 'approved' },
  ]) assert.equal(installationPolicy({ 'operation-mode': field }).mode, '');
});

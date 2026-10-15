// Narrow setup helper for the operator's already-installed test app. This uses
// the official pinned CLI clients/auth flow and never reads or prints token files.
import { createAppClient, createAppSettingsClient, createInstallationsClient, getHeaders }
  from '../node_modules/@devvit/cli/dist/util/clientGenerators.js';
import { NodeFetchRPC } from '../node_modules/@devvit/cli/dist/util/fetch-twirp-rpc.js';
import { getAccessToken } from '../node_modules/@devvit/cli/dist/util/auth.js';
import { DEVVIT_PORTAL_API } from '../node_modules/@devvit/cli/dist/util/config.js';
import { DevPortalInstallationSettingsClientJSON }
  from '@devvit/protos/types/devvit/dev_portal/dev_portal.twirp-client.js';
import { InstallationType } from '@devvit/protos/json/devvit/dev_portal/app_version/info/app_version_info.js';
import { FormFieldType } from '@devvit/protos/json/devvit/ui/form_builder/v1alpha/type.js';

const mode = process.argv[2] ?? 'inspect';
if (!['inspect', 'apply'].includes(mode)) throw new Error('Use inspect or apply.');
if (DEVVIT_PORTAL_API !== 'https://developers.reddit.com/api') throw new Error('Production Devvit portal required.');
const slug = 'user-helper', community = 'saurabhhelpertest', owner = 'saurabhimapro';
const reviewedOn = '2026-10-14'; // The operator explicitly confirmed review today.
const privacyUrl = 'https://www.reddit.com/r/saurabhhelpertest/s/L7mpUwJldM';
const contact = 'saurabhimapro@gmail.com';
const scalar = value => value?.stringValue ?? value?.selectionValue?.values?.[0] ?? '';
const string = value => ({ fieldType: FormFieldType.STRING, stringValue: value });
const apps = createAppClient(), globals = createAppSettingsClient();
const installations = createInstallationsClient();
const locals = new DevPortalInstallationSettingsClientJSON(NodeFetchRPC({
  baseUrl: `${DEVVIT_PORTAL_API}/installation-settings`, getToken: getAccessToken,
  headers: getHeaders('DevPortalInstallationSettings'),
}));
const appInfo = await apps.GetBySlug({ slug, hidePrereleaseVersions: false, limit: 1 });
const app = appInfo.app;
if (!app || app.slug !== slug || app.owner?.displayName.replace(/^u\//, '').toLowerCase() !== owner)
  throw new Error('App slug/owner did not match. No settings changed.');
const installed = await installations.GetByAppNameAndInstallLocation({
  slug, type: InstallationType.SUBREDDIT, location: `r/${community}`,
});
const installation = installed.installation;
if (!installation?.id || installation.location?.name.replace(/^r\//, '').toLowerCase() !== community
    || installed.app?.id !== app.id)
  throw new Error('Test installation did not match. No settings changed.');
const appBefore = await globals.GetSettings({ appId: app.id });
const localBefore = await locals.GetSettings({ installationId: installation.id });
const appValues = appBefore.settings?.settings ?? {};
const localValues = localBefore.settings?.settings ?? {};
const shape = (value, depth = 0) => value === null ? 'null' : typeof value !== 'object' ? typeof value
  : depth >= 5 ? 'object' : Object.fromEntries(Object.entries(value).slice(0, 20).map(([key, item]) => [key, shape(item, depth + 1)]));
if (mode === 'inspect') {
  const effective = { ...appValues, ...localValues };
  const localForm = await locals.GetForm({ installationId: installation.id });
  console.log(JSON.stringify({ slug, owner, community,
    appResponseShape: shape(appBefore), installationResponseShape: shape(localBefore),
    installedVersion: installed.appVersion && {
      major: installed.appVersion.majorVersion, minor: installed.appVersion.minorVersion,
      patch: installed.appVersion.patchVersion, prerelease: installed.appVersion.prereleaseVersion,
    },
    globalMode: scalar(appValues['operation-mode']),
    installationMode: scalar(localValues['operation-mode']),
    localFields: Object.values(localForm.form ?? {}).flatMap(form => form.fields.map(field => ({ id: field.fieldId, label: field.label, type: field.fieldType }))),
    mode: scalar(effective['operation-mode']),
    privacyUrl: scalar(effective['privacy-url']), contact: scalar(effective['deletion-contact']),
    scope: scalar(effective['approved-community']),
    permissionRecorded: !!scalar(effective['permission-reference']),
    communityPermissionRecorded: !!scalar(localValues['community-permission']),
    rulesReviewedOn: scalar(localValues['rules-reviewed-on']),
  }, null, 2));
} else {
  if (!['', 'disabled', 'playtest'].includes(scalar(localValues['operation-mode'])))
    throw new Error('Refusing to change a production installation with this playtest helper.');
  const localForm = await locals.GetForm({ installationId: installation.id });
  const fieldIds = Object.values(localForm.form ?? {}).flatMap(form => form.fields.map(field => field.fieldId));
  if (!fieldIds.includes('operation-mode') || !fieldIds.includes('privacy-url'))
    throw new Error('The updated community settings schema is not installed yet. Keep/restart the playtest and retry.');
  const updateLocal = async settings => {
    const result = await locals.UpdateSettings({ installationId: installation.id, shouldClear: [], settings: { settings, version: '' } });
    if (!result.success) throw new Error('Community settings validation failed: ' + JSON.stringify(result.errors));
  };
  const choice = value => ({ fieldType: FormFieldType.SELECTION, selectionValue: { values: [value] } });
  // Community settings support proper typed single-choice values. Keep disabled
  // until the complete configuration has been saved and read back.
  const prepared = { ...localValues,
    'operation-mode': choice('disabled'), 'approved-community': string(community),
    'deletion-contact': string(contact), 'privacy-url': string(privacyUrl),
    'permission-reference': string('Existing Devvit owner playtest of user-helper in r/saurabhhelpertest; production review pending'),
    'community-permission': string('Community creator u/saurabhimapro authorized owner testing in r/saurabhhelpertest'),
    'rules-reviewed-on': string(reviewedOn),
  };
  await updateLocal(prepared);
  const localAfter = await locals.GetSettings({ installationId: installation.id });
  if (scalar(localAfter.settings?.settings['rules-reviewed-on']) !== reviewedOn
      || !scalar(localAfter.settings?.settings['community-permission']))
    throw new Error('Installation readback failed. Workflow remains disabled.');
  await updateLocal({ ...prepared, 'operation-mode': choice('playtest') });
  const after = await locals.GetSettings({ installationId: installation.id });
  if (scalar(after.settings?.settings['operation-mode']) !== 'playtest'
      || scalar(after.settings?.settings['approved-community']) !== community
      || scalar(after.settings?.settings['privacy-url']) !== privacyUrl) {
    await updateLocal(prepared);
    throw new Error('Community settings readback failed. Workflow disabled again.');
  }
  console.log(JSON.stringify({ slug, owner, community, mode: 'playtest', reviewedOn,
    settingsVerified: true, productionApproved: false, commentPublished: false }, null, 2));
}

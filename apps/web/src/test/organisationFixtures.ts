import type { OrganisationUnit } from "../lib/api/types";

type TeamDefinition = readonly [code: string, name: string];
type OpsDefinition = readonly [
  code: string,
  name: string,
  teams: readonly TeamDefinition[],
];
type CommandDefinition = readonly [
  code: string,
  operations: readonly OpsDefinition[],
];

const hierarchy: readonly CommandDefinition[] = [
  [
    "DIGOC",
    [
      ["NCGI_A_OPS", "NCGI-A Ops", [["OSG_TEAM", "OSG Team"], ["CEDAR_TEAM", "Cedar Team"], ["QUARTZ_TEAM", "Quartz Team"]]],
      ["AURORA_OPS", "Aurora Ops", [["LANTERN_TEAM", "Lantern Team"], ["MOSAIC_TEAM", "Mosaic Team"], ["COMPASS_TEAM", "Compass Team"]]],
      ["VERTEX_OPS", "Vertex Ops", [["EMBER_TEAM", "Ember Team"], ["ATLAS_TEAM", "Atlas Team"], ["HARBOUR_TEAM", "Harbour Team"]]],
    ],
  ],
  [
    "SYGOC",
    [
      ["NIMBUS_OPS", "Nimbus Ops", [["BEACON_TEAM", "Beacon Team"], ["SLATE_TEAM", "Slate Team"], ["ORCHARD_TEAM", "Orchard Team"]]],
      ["PARALLAX_OPS", "Parallax Ops", [["LUMEN_TEAM", "Lumen Team"], ["NORTHSTAR_TEAM", "Northstar Team"], ["COPPER_TEAM", "Copper Team"]]],
      ["HORIZON_OPS", "Horizon Ops", [["ROWAN_TEAM", "Rowan Team"], ["VELA_TEAM", "Vela Team"], ["KEEL_TEAM", "Keel Team"]]],
    ],
  ],
  [
    "MYGOC",
    [
      ["MERIDIAN_OPS", "Meridian Ops", [["FLINT_TEAM", "Flint Team"], ["THISTLE_TEAM", "Thistle Team"], ["GRANITE_TEAM", "Granite Team"]]],
      ["SOLSTICE_OPS", "Solstice Ops", [["KESTREL_TEAM", "Kestrel Team"], ["JUNIPER_TEAM", "Juniper Team"], ["VALE_TEAM", "Vale Team"]]],
      ["FRONTIER_OPS", "Frontier Ops", [["TIDAL_TEAM", "Tidal Team"], ["GROVE_TEAM", "Grove Team"], ["PRISM_TEAM", "Prism Team"]]],
    ],
  ],
];

const unitId = (code: string) =>
  `unit-${code.toLowerCase().replace(/_(ops|team)$/, "").replaceAll("_", "-")}`;

const root: OrganisationUnit = {
  id: unitId("JIOC"),
  code: "JIOC",
  name: "JIOC",
  kind: "ROOT",
  parentId: null,
  staffingStatus: "ROUTING_POOL",
  version: 1,
};

export const organisationUnits: OrganisationUnit[] = [
  root,
  ...hierarchy.flatMap(([commandCode, operations]) => {
    const command: OrganisationUnit = {
      id: unitId(commandCode),
      code: commandCode,
      name: commandCode,
      kind: "COMMAND",
      parentId: root.id,
      staffingStatus: "ROUTING_POOL",
      version: 1,
    };
    return [
      command,
      ...operations.flatMap(([opsCode, opsName, teams]) => {
        const operationsGroup: OrganisationUnit = {
          id: unitId(opsCode),
          code: opsCode,
          name: opsName,
          kind: "OPS_GROUP",
          parentId: command.id,
          staffingStatus: "ROUTING_POOL",
          version: 1,
        };
        return [
          operationsGroup,
          ...teams.map(([teamCode, teamName]): OrganisationUnit => ({
            id: unitId(teamCode),
            code: teamCode,
            name: teamName,
            kind: "TEAM",
            parentId: operationsGroup.id,
            staffingStatus: "STAFFED",
            version: 1,
          })),
        ];
      }),
    ];
  }),
];

export function organisationUnit(code: string) {
  const unit = organisationUnits.find((candidate) => candidate.code === code);
  if (!unit) throw new Error(`Unknown organisation fixture: ${code}`);
  return unit;
}

export function organisationChildren(parentCode: string) {
  const parent = organisationUnit(parentCode);
  return organisationUnits.filter((unit) => unit.parentId === parent.id);
}

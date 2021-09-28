import { State } from "../reducers/genesets";

export const selectGeneSets = (state: any): State => state.geneSets;

export const selectIsUserStateDirty = (state: State): boolean => {
  const geneSets = selectGeneSets(state);

  return Boolean(geneSets.genesets.size);
};

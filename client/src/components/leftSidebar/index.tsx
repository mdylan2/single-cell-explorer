/* Core dependencies */
import React, { CSSProperties } from "react";
import { connect } from "react-redux";

/* App dependencies */
import Categorical from "../categorical";
import * as globals from "../../globals";
import DynamicScatterplot from "../scatterplot/scatterplot";
import TopLeftLogoAndTitle from "./topLeftLogoAndTitle";
import Continuous from "../continuous/continuous";

/* Styles */
export const STYLE_LEFT_SIDEBAR: CSSProperties = {
  /* x y blur spread color */
  borderRight: `1px solid ${globals.lightGrey}`,
  display: "flex",
  flexDirection: "column",
  height: "100%",
};

// @ts-expect-error ts-migrate(1238) FIXME: Unable to resolve signature of class decorator whe... Remove this comment to see the full error message
@connect((state) => ({
  // eslint-disable-next-line @typescript-eslint/no-explicit-any --- FIXME: disabled temporarily on migrate to TS.
  scatterplotXXaccessor: (state as any).controls.scatterplotXXaccessor,
  // eslint-disable-next-line @typescript-eslint/no-explicit-any --- FIXME: disabled temporarily on migrate to TS.
  scatterplotYYaccessor: (state as any).controls.scatterplotYYaccessor,
}))
class LeftSideBar extends React.Component {
  // eslint-disable-next-line @typescript-eslint/explicit-module-boundary-types --- FIXME: disabled temporarily on migrate to TS.
  render() {
    // @ts-expect-error ts-migrate(2339) FIXME: Property 'scatterplotXXaccessor' does not exist on... Remove this comment to see the full error message
    const { scatterplotXXaccessor, scatterplotYYaccessor } = this.props;
    return (
      <div style={STYLE_LEFT_SIDEBAR}>
        <TopLeftLogoAndTitle />
        <div
          style={{
            height: "100%",
            width: globals.leftSidebarWidth,
            overflowY: "auto",
          }}
        >
          <Categorical />
          <Continuous />
        </div>
        {scatterplotXXaccessor && scatterplotYYaccessor ? (
          <DynamicScatterplot />
        ) : null}
      </div>
    );
  }
}

export default LeftSideBar;

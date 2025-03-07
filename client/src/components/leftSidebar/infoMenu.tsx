/* Core dependencies */
import React from "react";
import { Button, Menu, MenuItem, Popover, Position } from "@blueprintjs/core";
import { IconNames } from "@blueprintjs/icons";

/* App dependencies */
import { IconNames as CXGIconNames } from "../icon";
import Icon from "../icon/icon";

interface Props {
  privacyURL?: string;
  tosURL?: string;
}

const InformationMenu = React.memo<Props>((props): JSX.Element => {
  const { tosURL, privacyURL } = props;
  return (
    <Popover
      content={
        <Menu>
          <MenuItem
            href="https://join-cellxgene-users.herokuapp.com/"
            icon={<Icon icon={CXGIconNames.SLACK} />}
            target="_blank"
            text="Chat"
            rel="noopener"
          />
          <MenuItem
            icon={<Icon icon={CXGIconNames.ABOUT} />}
            popoverProps={{ openOnTargetFocus: false }}
            text="About cellxgene"
          >
            {tosURL && (
              <MenuItem
                href={tosURL}
                rel="noopener"
                target="_blank"
                text="Terms of Service"
              />
            )}
            {privacyURL && (
              <MenuItem
                href={privacyURL}
                rel="noopener"
                target="_blank"
                text="Privacy Policy"
              />
            )}
          </MenuItem>
        </Menu>
      }
      position={Position.BOTTOM_LEFT}
      modifiers={{
        preventOverflow: { enabled: false },
        hide: { enabled: false },
      }}
    >
      <Button data-testid="menu" icon={IconNames.MENU} minimal type="button" />
    </Popover>
  );
});

export default InformationMenu;

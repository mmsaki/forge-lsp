// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

interface IC {
    struct User {
        uint256 id;
        string first;
    }
}

contract C {
    function get(IC.User memory name) public pure {
        name.id;
    }
}

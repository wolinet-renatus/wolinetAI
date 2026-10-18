//go:build !xpack && !enterprise

package xpack

import "wolinet.ai/1apanel/core/utils/xpack/helper"

var AuthProvider = helper.NewIAuthProvider()

var MultiNodeProvider = helper.NewIMultiNodeProvider()
